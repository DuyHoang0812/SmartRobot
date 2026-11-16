// Exercise the real config loader/saver against an in-memory NVS API double.
#include "config.h"
#include "nvs.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct { const char *key; uint32_t value; } entry_t;
static entry_t entries[24];
static unsigned count, commits;
static int writes_allowed;
int nvs_flash_init_partition(const char *name) { assert(!strcmp(name, "robot_cfg")); return ESP_OK; }
int nvs_open_from_partition(const char *part, const char *space, int mode, nvs_handle_t *out)
{
    assert(!strcmp(part, "robot_cfg") && !strcmp(space, "robot"));
    *out = mode; return ESP_OK;
}
int nvs_get_str(nvs_handle_t h, const char *key, char *out, size_t *size)
{
    (void)h;
    const char *value = !strcmp(key, "ssid") ? "test-wifi"
        : !strcmp(key, "wifi_pass") ? ""
        : !strcmp(key, "base_url") ? "https://robot.example.test/api/v1/devices"
        : !strcmp(key, "device_id") ? "test-device"
        : !strcmp(key, "secret") ? "unit-test-only-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" : NULL;
    if (!value) return ESP_FAIL;
    size_t length = strlen(value) + 1;
    if (out) { assert(*size >= length); memcpy(out, value, length); }
    *size = length; return ESP_OK;
}
int nvs_get_u32(nvs_handle_t h, const char *key, uint32_t *out)
{
    (void)h;
    for (unsigned i = 0; i < count; ++i) if (!strcmp(entries[i].key, key)) {
        *out = entries[i].value; return ESP_OK;
    }
    return ESP_FAIL;
}
int nvs_get_u8(nvs_handle_t h, const char *key, uint8_t *out)
{
    uint32_t value;
    int error = nvs_get_u32(h, key, &value);
    if (error == ESP_OK) *out = value;
    return error;
}
int nvs_set_u32(nvs_handle_t h, const char *key, uint32_t value)
{
    assert(h == NVS_READWRITE);
    if (!writes_allowed) return ESP_FAIL;
    if (writes_allowed > 0) --writes_allowed;
    for (unsigned i = 0; i < count; ++i) if (!strcmp(entries[i].key, key)) {
        entries[i].value = value; return ESP_OK;
    }
    assert(count < 24); entries[count++] = (entry_t){key, value}; return ESP_OK;
}
int nvs_set_u8(nvs_handle_t h, const char *key, uint8_t value) { return nvs_set_u32(h, key, value); }
int nvs_commit(nvs_handle_t h) { assert(h == NVS_READWRITE); ++commits; return ESP_OK; }
void nvs_close(nvs_handle_t h) { (void)h; }
static void put(const char *key, uint32_t value) { assert(nvs_set_u32(NVS_READWRITE, key, value) == ESP_OK); }
static robot_config_t load(void) { robot_config_t c; assert(config_load(&c) == ESP_OK); return c; }
int main(void)
{
    writes_allowed = -1;
    robot_config_t c = load();
    assert(c.left_motor_percent == 100 && c.right_motor_percent == 83.5f);
    assert(c.auto_clearance_cm == 15 && c.auto_backup_ms == 400);
    put("left_pct", 90); put("right_pct", 100);
    put("auto_clear", 30); put("auto_back_ms", 300);
    put("auto_left_ms", 400); put("auto_right_ms", 400);
    c = load();
    assert(c.left_motor_percent == 100 && c.right_motor_percent == 83.5f
        && c.auto_clearance_cm == 15 && c.auto_backup_ms == 400);
    assert(commits == 0); // Loading never rewrites flash or credentials.
    uint32_t stored; assert(nvs_get_u32(0, "left_pct", &stored) == ESP_OK && stored == 90);
    put("left_pct", 105); put("trim_rev", 11);
    c = load(); assert(c.left_motor_percent == 100 && c.right_motor_percent == 83.5f);
    put("left_pct", 85); put("trim_rev", 12);
    c = load(); assert(c.left_motor_percent == 100 && c.right_motor_percent == 83.5f);
    put("left_pct", 100); put("right_pct", 85); put("trim_rev", 13);
    c = load(); assert(c.left_motor_percent == 100 && c.right_motor_percent == 83.5f);
    put("right_pct", 80); put("trim_rev", 14);
    c = load(); assert(c.left_motor_percent == 100 && c.right_motor_percent == 83.5f);
    put("right_pct", 82); put("trim_rev", 15);
    c = load(); assert(c.right_motor_percent == 83.5f);
    put("right_pct", 100);
    put("left_pct", 82); put("auto_left_ms", 500);
    c = load();
    assert(c.left_motor_percent == 82 && c.right_motor_percent == 100);
    assert(c.auto_clearance_cm == 30 && c.auto_backup_ms == 300 && c.auto_turn_left_ms == 500);
    // Explicit new calibration can still choose the historical values and survive reboot.
    assert(config_save_motor_trim(90, 100) == ESP_OK);
    assert(config_save_auto(30, 300, 400, 400) == ESP_OK);
    c = load();
    assert(c.left_motor_percent == 90 && c.auto_clearance_cm == 30 && c.auto_backup_ms == 300);
    assert(commits == 2);
    assert(config_save_motor_trim(49, 100) == ESP_ERR_INVALID_ARG);
    assert(config_save_auto(14, 400, 400, 400) == ESP_ERR_INVALID_ARG);
    assert(commits == 2);
    assert(config_save_motor_trim(100, 83.5f) == ESP_OK);
    c = load(); assert(c.left_motor_percent == 100 && c.right_motor_percent == 83.5f);
    assert(nvs_get_u32(0, "right_pct10", &stored) == ESP_OK && stored == 835);
    assert(commits == 3);
    writes_allowed = 1;
    assert(config_save_auto(15, 400, 400, 400) == ESP_FAIL && commits == 3);
    puts("Config assertions passed");
    return 0;
}
