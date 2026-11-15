#include "hardware.h"
#include "board.h"
#include "robot.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static TaskHandle_t worker;
static portMUX_TYPE pulse_lock = portMUX_INITIALIZER_UNLOCKED;
static volatile int64_t rise, fall;
static volatile bool waiting;

static void echo_isr(void *argument)
{
    (void)argument;
    int level = gpio_get_level(PIN_ECHO);
    int64_t now = esp_timer_get_time();
    BaseType_t wake = pdFALSE;
    portENTER_CRITICAL_ISR(&pulse_lock);
    if (waiting) {
        if (level) rise = now;
        else if (rise && !fall) {
            fall = now;
            vTaskNotifyGiveFromISR(worker, &wake);
        }
    }
    portEXIT_CRITICAL_ISR(&pulse_lock);
    if (wake) portYIELD_FROM_ISR();
}

static void sensor_task(void *argument)
{
    (void)argument;
    worker = xTaskGetCurrentTaskHandle();
    for (;;) {
        sensor_reading_t sample = {0};
        int64_t pose;
        robot_servo_pose(&sample.angle, &pose);
        ulTaskNotifyTake(pdTRUE, 0);
        portENTER_CRITICAL(&pulse_lock);
        rise = fall = 0; waiting = true;
        portEXIT_CRITICAL(&pulse_lock);
        bool echo_stuck = gpio_get_level(PIN_ECHO) != 0;
        if (!echo_stuck) {
            gpio_set_level(PIN_TRIG, 0); esp_rom_delay_us(2);
            gpio_set_level(PIN_TRIG, 1); esp_rom_delay_us(10);
            gpio_set_level(PIN_TRIG, 0);
            ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(30));
        }
        portENTER_CRITICAL(&pulse_lock);
        waiting = false;
        int64_t width = fall > rise && rise ? fall - rise : 0;
        portEXIT_CRITICAL(&pulse_lock);
        sample.at_us = esp_timer_get_time();
        sample.distance_cm = width * 0.0343f / 2.0f;
        sample.valid = !echo_stuck && width > 0 && width <= 25000
            && sample.distance_cm >= 2.0f && sample.distance_cm <= 400.0f;
        robot_sensor_publish(sample, pose);
        vTaskDelay(pdMS_TO_TICKS(60)); // Separate bounded task, never blocks watchdog or control.
    }
}

esp_err_t sensor_start(void)
{
    gpio_config_t trigger = {.pin_bit_mask = 1ULL << PIN_TRIG, .mode = GPIO_MODE_OUTPUT};
    esp_err_t e = gpio_config(&trigger);
    if (e != ESP_OK) return e;
    gpio_set_level(PIN_TRIG, 0);
    gpio_config_t echo = {.pin_bit_mask = 1ULL << PIN_ECHO, .mode = GPIO_MODE_INPUT,
        .pull_down_en = GPIO_PULLDOWN_ENABLE, .intr_type = GPIO_INTR_ANYEDGE};
    if ((e = gpio_config(&echo)) != ESP_OK) return e;
    // Non-IRAM service: no claim that flash stalls can still sample; stale data stops motion.
    e = gpio_install_isr_service(0);
    if (e != ESP_OK) return e;
    if ((e = gpio_isr_handler_add(PIN_ECHO, echo_isr, NULL)) != ESP_OK) return e;
    return xTaskCreatePinnedToCore(sensor_task, "hcsr04", 3072, NULL, 6, NULL, 1) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
