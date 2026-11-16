#include "hardware.h"
#include "config.h"
#include "board.h"
#include "driver/gpio.h"
#include "driver/ledc.h"

static bool ready;
static movement_t previous;
static uint8_t previous_speed;
static float left_percent = DEFAULT_LEFT_MOTOR_PERCENT, right_percent = DEFAULT_RIGHT_MOTOR_PERCENT;
static uint8_t left_duty, right_duty;
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
    left_duty = right_duty = 0;
}

void motor_set_trim(float left, float right)
{
    motor_stop(); left_percent = left; right_percent = right;
}
void motor_get_duties(uint8_t *left, uint8_t *right) { *left = left_duty; *right = right_duty; }
static uint8_t scaled(uint8_t speed, float percent)
{
    uint32_t value = (uint32_t)(speed * percent / 100.0f + 0.5f);
    return value > 255 ? 255 : (uint8_t)value;
}

esp_err_t motor_set(movement_t movement, uint8_t speed)
{
    if (movement == MOVE_STOP || !speed) { motor_stop(); return ESP_OK; }
    if (!ready) return ESP_ERR_INVALID_STATE;
    if (movement == previous && speed == previous_speed) return ESP_OK;
    // Zero both inputs before polarity changes; PWM is on IN pins, NOT invented ENA/ENB pins.
    motor_stop();
    // Confirmed wiring: OUT1/2 (IN1/2) = RIGHT; OUT3/4 (IN3/4) = LEFT.
    // Pivot polarity corrected from the user's on-vehicle test (6b-8).
    // Forward/backward and per-wheel trim remain independent of this correction.
    const bool high[5][4] = {{0,0,0,0}, {1,0,1,0}, {0,1,0,1}, {0,1,1,0}, {1,0,0,1}};
    if (movement < MOVE_FORWARD || movement > MOVE_RIGHT) return ESP_ERR_INVALID_ARG;
    uint8_t left = scaled(speed, left_percent), right = scaled(speed, right_percent);
    for (int i = 0; i < 4; ++i) {
        uint8_t duty = i < 2 ? right : left;
        esp_err_t e = ledc_set_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i, high[movement][i] ? duty : 0);
        if (e == ESP_OK) e = ledc_update_duty(LEDC_LOW_SPEED_MODE, (ledc_channel_t)i);
        if (e != ESP_OK) { motor_stop(); return e; }
    }
    previous = movement; previous_speed = speed;
    left_duty = left; right_duty = right;
    return ESP_OK;
}
