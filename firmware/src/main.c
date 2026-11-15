
#include "config.h"
#include "hardware.h"
#include "robot.h"
#include "wifi.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

void safety_task(void *argument);
void device_task(void *argument);
void console_task(void *argument);
static robot_config_t config;

static void controller_task(void *argument)
{
    (void)argument;
    TickType_t wake = xTaskGetTickCount();
    for (;;) { robot_controller_tick(); vTaskDelayUntil(&wake, pdMS_TO_TICKS(10)); }
}
static void safe_halt(const char *message)
{
    robot_fault(true); buzzer_set(false);
    ESP_LOGE("startup", "%s; outputs disabled", message);
    for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
}
void app_main(void)
{
    // No credentials in firmware image, source, command-line arguments or logs.
    esp_log_level_set("HTTP_CLIENT", ESP_LOG_NONE);
    esp_log_level_set("wifi", ESP_LOG_WARN);
    if (outputs_init() != ESP_OK) safe_halt("GPIO initialization failed");
    if (motor_init() != ESP_OK || servo_init() != ESP_OK) safe_halt("Actuator initialization failed");
    if (config_load(&config) != ESP_OK) safe_halt("Missing/invalid robot_cfg NVS; provision configuration");
    if (robot_init(&config) != ESP_OK) safe_halt("Control initialization failed");
    if (xTaskCreatePinnedToCore(safety_task, "safety", 3072, NULL, 10, NULL, 1) != pdPASS)
        safe_halt("Watchdog task unavailable");
    if (sensor_start() != ESP_OK) safe_halt("Sensor initialization failed");
    if (xTaskCreatePinnedToCore(controller_task, "controller", 4096, NULL, 8, NULL, 1) != pdPASS)
        safe_halt("Control task unavailable");
    if (wifi_start(&config) != ESP_OK) { robot_fault(true); safe_halt("Wi-Fi initialization failed"); }
    if (xTaskCreatePinnedToCore(device_task, "device_http", 12288, &config, 4, NULL, 0) != pdPASS)
        safe_halt("Device task unavailable");
    if (xTaskCreate(console_task, "local_console", 3072, NULL, 2, NULL) != pdPASS)
        safe_halt("Console unavailable");
    ESP_LOGI("startup", "SmartRobot ready: ESP-IDF, 4MB target, no automatic motor activation");
    ESP_LOGI("startup", "Motor outputs armed: %s; blind Manual opt-in: %s",
        config.motors_enabled ? "yes" : "no", config.allow_blind_manual ? "yes" : "no");
}
