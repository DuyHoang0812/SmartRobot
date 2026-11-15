#include "hardware.h"
#include "board.h"
#include "driver/ledc.h"

esp_err_t servo_set_angle(int angle)
{
    if (angle < 0 || angle > 180) return ESP_ERR_INVALID_ARG;
    uint32_t pulse_us = 500 + (1900 * angle / 180);
    uint32_t duty = pulse_us * 65536UL / 20000;
    esp_err_t e = ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_4, duty);
    return e == ESP_OK ? ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_4) : e;
}

esp_err_t servo_init(void)
{
    ledc_timer_config_t timer = {.speed_mode = LEDC_LOW_SPEED_MODE, .timer_num = LEDC_TIMER_1,
        .duty_resolution = LEDC_TIMER_16_BIT, .freq_hz = 50, .clk_cfg = LEDC_AUTO_CLK};
    esp_err_t e = ledc_timer_config(&timer);
    if (e != ESP_OK) return e;
    ledc_channel_config_t channel = {.gpio_num = PIN_SERVO, .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_4, .timer_sel = LEDC_TIMER_1, .intr_type = LEDC_INTR_DISABLE,
        .duty = 1450UL * 65536 / 20000};
    return ledc_channel_config(&channel);
}
