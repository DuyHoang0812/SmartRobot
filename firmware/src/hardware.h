#pragma once
#include "esp_err.h"
#include "types.h"

// Motor/output functions are serialized by robot.c's mutex (init precedes all tasks).
esp_err_t motor_init(void);
esp_err_t motor_set(movement_t movement, uint8_t speed);
void motor_stop(void);
void motor_set_trim(float left_percent, float right_percent);
void motor_get_duties(uint8_t *left, uint8_t *right);
esp_err_t servo_init(void);
esp_err_t servo_set_angle(int angle);
esp_err_t outputs_init(void);
void buzzer_set(bool on);
void relay_set(bool on);
esp_err_t sensor_start(void);
