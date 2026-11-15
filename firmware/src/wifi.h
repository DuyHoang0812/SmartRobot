#pragma once
#include "config.h"
#include "esp_err.h"
esp_err_t wifi_start(const robot_config_t *config);
bool wifi_connected(void);
uint32_t wifi_epoch(void);
