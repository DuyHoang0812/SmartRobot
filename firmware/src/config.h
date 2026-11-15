#pragma once
#include "esp_err.h"
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    char ssid[33], password[65], base_url[256], device_id[129], secret[129];
    char ntp_server[128];
    char *ca_pem;
    bool allow_http, motors_enabled, allow_blind_manual, relay_console;
    uint8_t full_speed, slow_speed, turn_speed;
    uint32_t blind_ms, http_timeout_ms;
} robot_config_t;

esp_err_t config_load(robot_config_t *config);
