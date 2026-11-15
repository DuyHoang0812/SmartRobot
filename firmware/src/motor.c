#include "hardware.h"
#include "board.h"
#include "driver/gpio.h"
#include "driver/ledc.h"

static bool ready;
static movement_t previous;
static uint8_t previous_speed;
static const int pins[] = {PIN_IN1, PIN_IN2, PIN_IN3, PIN_IN4};

esp_err_t motor_init(void)
{
    for (int i = 0; i < 4; ++i) {
        gpio_set_level(pins[i], 0);
        gpio_set_direction(pins[i], GPIO_MODE_OUTPUT);
    }
    ledc_timer_config_t timer = {.speed_mode = LEDC_LOW_SPEED_MODE, .timer_num = LEDC_TIMER_0,
        .duty_resolution = LEDC_TIMER_8_BIT, .freq_hz = 1000, .clk_cfg = LEDC_AUTO_CLK};
    esp_err_t e = ledc_timer_config(&timer);
    if (e != ESP_OK) return e;
    for (int i = 0; i < 4; ++i) {
        ledc_channel_config_t channel = {.gpio_num = pins[i], .speed_mode = LEDC_LOW_SPEED_MODE,
            .channel = (ledc_channel_t)i, .timer_sel = LEDC_TIMER_0, .duty = 0,
            .intr_type = LEDC_INTR_DISABLE};
        if ((e = ledc_channel_config(&channel)) != ESP_OK) return e;
    }
    ready = true;
    return ESP_OK;
}

void motor_stop(void)
{
    if (ready) for (int i = 0; i < 4; ++i) ledc_stop(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i, 0);
    else for (int i = 0; i < 4; ++i) gpio_set_level(pins[i], 0);
    previous = MOVE_STOP; previous_speed = 0;
}

esp_err_t motor_set(movement_t movement, uint8_t speed)
{
    if (movement == MOVE_STOP || !speed) { motor_stop(); return ESP_OK; }
    if (!ready) return ESP_ERR_INVALID_STATE;
    if (movement == previous && speed == previous_speed) return ESP_OK;
    // Zero both inputs before polarity changes; PWM is on IN pins, NOT invented ENA/ENB pins.
    motor_stop();
    const bool high[5][4] = {{0,0,0,0}, {1,0,1,0}, {0,1,0,1}, {0,1,1,0}, {1,0,0,1}};
    if (movement < MOVE_FORWARD || movement > MOVE_RIGHT) return ESP_ERR_INVALID_ARG;
    for (int i = 0; i < 4; ++i) {
        esp_err_t e = ledc_set_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i, high[movement][i] ? speed : 0);
        if (e == ESP_OK) e = ledc_update_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i);
        if (e != ESP_OK) { motor_stop(); return e; }
    }
    previous = movement; previous_speed = speed;
    return ESP_OK;
}
