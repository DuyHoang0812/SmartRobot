#pragma once
#include "esp_err.h"
#include <stdbool.h>
#include <stdint.h>

#define DEFAULT_LEFT_MOTOR_PERCENT 100
#define DEFAULT_RIGHT_MOTOR_PERCENT 83.5f
// Motion timings and clearance from ver2_6_esp32.ino.
#define DEFAULT_AUTO_CLEARANCE_CM 15
#define DEFAULT_AUTO_BACKUP_MS 400
#define DEFAULT_AUTO_TURN_MS 400
#define CONFIG_TUNING_REVISION 10
#define CONFIG_TRIM_REVISION 16

typedef struct {
    char ssid[33], password[65], base_url[256], device_id[129], secret[129];
    char ntp_server[128];
    char *ca_pem;
    bool allow_http, motors_enabled, allow_blind_manual, relay_console;
    uint8_t full_speed, slow_speed, turn_speed;
    uint32_t blind_ms, http_timeout_ms;
    float left_motor_percent, right_motor_percent;
    uint32_t auto_clearance_cm, auto_backup_ms, auto_turn_left_ms, auto_turn_right_ms;
} robot_config_t;

esp_err_t config_load(robot_config_t *config);
esp_err_t config_save_motor_trim(float left_percent, float right_percent);
esp_err_t config_save_auto(uint32_t clearance_cm, uint32_t backup_ms, uint32_t left_ms, uint32_t right_ms);
