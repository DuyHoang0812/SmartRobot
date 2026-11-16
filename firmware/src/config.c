#include "config.h"
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "nvs.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"

static esp_err_t string(nvs_handle_t nvs, const char *key, char *dst, size_t cap)
{
    size_t length = cap;
    return nvs_get_str(nvs, key, dst, &length);
}

static bool flag(nvs_handle_t nvs, const char *key)
{
    uint8_t value = 0;
    nvs_get_u8(nvs, key, &value);
    return value == 1;
}

esp_err_t config_load(robot_config_t *c)
{
    memset(c, 0, sizeof(*c));
    c->full_speed = 75; c->slow_speed = 30; c->turn_speed = 75;
    c->blind_ms = 300; c->http_timeout_ms = 250;
    c->left_motor_percent = DEFAULT_LEFT_MOTOR_PERCENT;
    c->right_motor_percent = DEFAULT_RIGHT_MOTOR_PERCENT;
    c->auto_clearance_cm = DEFAULT_AUTO_CLEARANCE_CM;
    c->auto_backup_ms = DEFAULT_AUTO_BACKUP_MS;
    c->auto_turn_left_ms = c->auto_turn_right_ms = DEFAULT_AUTO_TURN_MS;
    strcpy(c->ntp_server, "pool.ntp.org");
    esp_err_t error = nvs_flash_init_partition("robot_cfg");
    if (error != ESP_OK) return error; // Never erase a provisioned partition automatically.
    nvs_handle_t nvs;
    error = nvs_open_from_partition("robot_cfg", "robot", NVS_READONLY, &nvs);
    if (error != ESP_OK) return error;
    error = string(nvs, "ssid", c->ssid, sizeof(c->ssid));
    if (error == ESP_OK) error = string(nvs, "wifi_pass", c->password, sizeof(c->password));
    if (error == ESP_OK) error = string(nvs, "base_url", c->base_url, sizeof(c->base_url));
    if (error == ESP_OK) error = string(nvs, "device_id", c->device_id, sizeof(c->device_id));
    if (error == ESP_OK) error = string(nvs, "secret", c->secret, sizeof(c->secret));
    c->allow_http = flag(nvs, "allow_http");
    c->motors_enabled = flag(nvs, "motors_on");
    c->allow_blind_manual = flag(nvs, "blind_manual");
    c->relay_console = flag(nvs, "relay_console");
    nvs_get_u8(nvs, "full_speed", &c->full_speed);
    nvs_get_u8(nvs, "slow_speed", &c->slow_speed);
    nvs_get_u8(nvs, "turn_speed", &c->turn_speed);
    nvs_get_u32(nvs, "blind_ms", &c->blind_ms);
    nvs_get_u32(nvs, "http_ms", &c->http_timeout_ms);
    uint32_t trim;
    if (nvs_get_u32(nvs, "left_pct", &trim) == ESP_OK) c->left_motor_percent = trim;
    if (nvs_get_u32(nvs, "right_pct", &trim) == ESP_OK) c->right_motor_percent = trim;
    if (nvs_get_u32(nvs, "left_pct10", &trim) == ESP_OK) c->left_motor_percent = trim / 10.0f;
    if (nvs_get_u32(nvs, "right_pct10", &trim) == ESP_OK) c->right_motor_percent = trim / 10.0f;
    nvs_get_u32(nvs, "auto_clear", &c->auto_clearance_cm);
    nvs_get_u32(nvs, "auto_back_ms", &c->auto_backup_ms);
    nvs_get_u32(nvs, "auto_left_ms", &c->auto_turn_left_ms);
    nvs_get_u32(nvs, "auto_right_ms", &c->auto_turn_right_ms);
    uint8_t trim_revision = 0, auto_revision = 0;
    nvs_get_u8(nvs, "trim_rev", &trim_revision);
    nvs_get_u8(nvs, "auto_rev", &auto_revision);
    // Upgrade only the exact old shipped presets, without rewriting credentials/NVS.
    // New saves carry a revision so explicitly choosing these values remains possible.
    bool old_trim = (c->right_motor_percent == 100
        && (c->left_motor_percent == 85 || c->left_motor_percent == 90 || c->left_motor_percent == 105))
        || (c->left_motor_percent == 100 && (c->right_motor_percent == 85
            || c->right_motor_percent == 80 || c->right_motor_percent == 82));
    if (trim_revision < CONFIG_TRIM_REVISION && old_trim) {
        c->left_motor_percent = DEFAULT_LEFT_MOTOR_PERCENT;
        c->right_motor_percent = DEFAULT_RIGHT_MOTOR_PERCENT;
        ESP_LOGI("config", "Wheel preset updated to LEFT=100%% RIGHT=83.5%%");
    }
    if (auto_revision < CONFIG_TUNING_REVISION && c->auto_clearance_cm == 30
        && c->auto_backup_ms == 300 && c->auto_turn_left_ms == 400 && c->auto_turn_right_ms == 400) {
        c->auto_clearance_cm = DEFAULT_AUTO_CLEARANCE_CM;
        c->auto_backup_ms = DEFAULT_AUTO_BACKUP_MS;
        ESP_LOGI("config", "Legacy Auto preset upgraded to ver2_6: clearance=15cm backup=400ms turn=400ms");
    }
    string(nvs, "ntp", c->ntp_server, sizeof(c->ntp_server));
    size_t ca_size = 0;
    if (nvs_get_str(nvs, "ca_pem", NULL, &ca_size) == ESP_OK && ca_size > 1 && ca_size <= 4000) {
        c->ca_pem = calloc(1, ca_size);
        if (!c->ca_pem) error = ESP_ERR_NO_MEM;
        else if (nvs_get_str(nvs, "ca_pem", c->ca_pem, &ca_size) != ESP_OK) error = ESP_FAIL;
    }
    nvs_close(nvs);
    if (error != ESP_OK) return error;
    size_t url_len = strlen(c->base_url), id_len = strlen(c->device_id);
    const char *suffix = "/api/v1/devices";
    if (!c->ssid[0] || id_len < 3 || strlen(c->secret) < 32 || url_len < strlen(suffix)
        || strcmp(c->base_url + url_len - strlen(suffix), suffix) != 0
        || strpbrk(c->base_url, "?#@\r\n ") || strpbrk(c->secret, "\r\n")
        || (strncmp(c->base_url, "https://", 8) != 0 &&
            !(c->allow_http && strncmp(c->base_url, "http://", 7) == 0))
        || c->slow_speed > c->full_speed || !c->slow_speed || !c->turn_speed
        || c->blind_ms < 50 || c->blind_ms > 400 || c->http_timeout_ms < 50
        || c->http_timeout_ms > 400
        || !isfinite(c->left_motor_percent) || !isfinite(c->right_motor_percent)
        || c->left_motor_percent < 50 || c->left_motor_percent > 150
        || c->right_motor_percent < 50 || c->right_motor_percent > 150
        || c->auto_clearance_cm < 15 || c->auto_clearance_cm > 100
        || c->auto_backup_ms < 50 || c->auto_backup_ms > 400
        || c->auto_turn_left_ms < 100 || c->auto_turn_left_ms > 1200
        || c->auto_turn_right_ms < 100 || c->auto_turn_right_ms > 1200) return ESP_ERR_INVALID_ARG;
    for (const char *p = c->device_id; *p; ++p)
        if (!(isalnum((unsigned char)*p) || strchr("_.:-", *p))) return ESP_ERR_INVALID_ARG;
    for (const char *p = c->secret; *p; ++p)
        if ((unsigned char)*p <= 32 || (unsigned char)*p >= 127) return ESP_ERR_INVALID_ARG;
    if (!strncmp(c->base_url, "http://", 7)) {
        char host[64];
        size_t length = strcspn(c->base_url + 7, ":/");
        if (!length || length >= sizeof(host)) return ESP_ERR_INVALID_ARG;
        memcpy(host, c->base_url + 7, length); host[length] = 0;
        struct in_addr addr;
        if (inet_pton(AF_INET, host, &addr) != 1) return ESP_ERR_INVALID_ARG;
        uint32_t ip = ntohl(addr.s_addr);
        bool private = (ip >> 24) == 10 || (ip >> 20) == 0xac1
            || (ip >> 16) == 0xc0a8 || (ip >> 16) == 0xa9fe;
        if (!private) return ESP_ERR_INVALID_ARG;
    }
    return ESP_OK;
}

esp_err_t config_save_motor_trim(float left_percent, float right_percent)
{
    if (!isfinite(left_percent) || !isfinite(right_percent)
        || left_percent < 50 || left_percent > 150 || right_percent < 50 || right_percent > 150)
        return ESP_ERR_INVALID_ARG;
    nvs_handle_t nvs;
    esp_err_t error = nvs_open_from_partition("robot_cfg", "robot", NVS_READWRITE, &nvs);
    if (error != ESP_OK) return error;
    error = nvs_set_u32(nvs, "left_pct10", (uint32_t)(left_percent * 10 + 0.5f));
    if (error == ESP_OK) error = nvs_set_u32(nvs, "right_pct10", (uint32_t)(right_percent * 10 + 0.5f));
    if (error == ESP_OK) error = nvs_set_u8(nvs, "trim_rev", CONFIG_TRIM_REVISION);
    if (error == ESP_OK) error = nvs_commit(nvs);
    nvs_close(nvs);
    return error;
}

esp_err_t config_save_auto(uint32_t clearance_cm, uint32_t backup_ms, uint32_t left_ms, uint32_t right_ms)
{
    if (clearance_cm < 15 || clearance_cm > 100 || backup_ms < 50 || backup_ms > 400
        || left_ms < 100 || left_ms > 1200 || right_ms < 100 || right_ms > 1200)
        return ESP_ERR_INVALID_ARG;
    nvs_handle_t nvs;
    esp_err_t error = nvs_open_from_partition("robot_cfg", "robot", NVS_READWRITE, &nvs);
    if (error != ESP_OK) return error;
    error = nvs_set_u32(nvs, "auto_clear", clearance_cm);
    if (error == ESP_OK) error = nvs_set_u32(nvs, "auto_back_ms", backup_ms);
    if (error == ESP_OK) error = nvs_set_u32(nvs, "auto_left_ms", left_ms);
    if (error == ESP_OK) error = nvs_set_u32(nvs, "auto_right_ms", right_ms);
    if (error == ESP_OK) error = nvs_set_u8(nvs, "auto_rev", CONFIG_TUNING_REVISION);
    if (error == ESP_OK) error = nvs_commit(nvs);
    nvs_close(nvs);
    return error;
}
