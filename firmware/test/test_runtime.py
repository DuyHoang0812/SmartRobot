"""Compile the real controller/motor C modules with host-only ESP-IDF API doubles."""

import pathlib
import subprocess
import tempfile
import unittest

STUBS = {
    "esp_err.h": """#pragma once
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_ERR_NO_MEM 1
#define ESP_ERR_INVALID_STATE 2
#define ESP_ERR_INVALID_ARG 3
#define ESP_FAIL -1
#define ESP_ERROR_CHECK(x) ((void)(x))
static inline const char *esp_err_to_name(int error) { (void)error; return "host error"; }
""",
    "esp_log.h": """#pragma once
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
""",
    "esp_timer.h": """#pragma once
#include <stdint.h>
int64_t esp_timer_get_time(void);
""",
    "esp_task_wdt.h": """#pragma once
static inline int esp_task_wdt_add(void *task) { (void)task; return 0; }
static inline int esp_task_wdt_reset(void) { return 0; }
""",
    "freertos/FreeRTOS.h": """#pragma once
#include <stddef.h>
#define portMAX_DELAY 0
#define pdMS_TO_TICKS(ms) (ms)
""",
    "freertos/semphr.h": """#pragma once
typedef int SemaphoreHandle_t;
static inline int xSemaphoreCreateMutex(void) { return 1; }
static inline void xSemaphoreTake(int m, int t) { (void)m; (void)t; }
static inline void xSemaphoreGive(int m) { (void)m; }
""",
    "freertos/task.h": """#pragma once
#ifdef DEVICE_RETRY_TEST
void test_delay(int ms);
static inline void vTaskDelay(int ms) { test_delay(ms); }
#else
static inline void vTaskDelay(int ms) { (void)ms; }
#endif
""",
    "driver/gpio.h": """#pragma once
#define GPIO_MODE_OUTPUT 1
#define GPIO_INTR_DISABLE 0
#include <stdint.h>
typedef struct { uint64_t pin_bit_mask; int mode, intr_type; } gpio_config_t;
int gpio_config(const gpio_config_t *config);
int gpio_set_level(int pin, int level);
int gpio_set_direction(int pin, int mode);
""",
    "driver/ledc.h": """#pragma once
#include <stdint.h>
typedef int ledc_channel_t;
#define LEDC_LOW_SPEED_MODE 0
#define LEDC_TIMER_0 0
#define LEDC_TIMER_8_BIT 8
#define LEDC_AUTO_CLK 0
#define LEDC_INTR_DISABLE 0
typedef struct { int speed_mode, timer_num, duty_resolution, freq_hz, clk_cfg; } ledc_timer_config_t;
typedef struct { int gpio_num, speed_mode, channel, timer_sel, duty, intr_type; } ledc_channel_config_t;
int ledc_timer_config(const ledc_timer_config_t *timer);
int ledc_channel_config(const ledc_channel_config_t *channel);
int ledc_stop(int mode, int channel, int idle);
int ledc_set_duty(int mode, int channel, uint32_t duty);
int ledc_update_duty(int mode, int channel);
""",
    "esp_random.h": """#pragma once
#include <string.h>
static inline void esp_fill_random(void *out, size_t n) { memset(out, 7, n); }
""",
    "nvs.h": """#pragma once
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
typedef int nvs_handle_t;
#define NVS_READONLY 0
#define NVS_READWRITE 1
int nvs_open_from_partition(const char *, const char *, int, nvs_handle_t *);
int nvs_get_str(nvs_handle_t, const char *, char *, size_t *);
int nvs_get_u8(nvs_handle_t, const char *, uint8_t *);
int nvs_get_u32(nvs_handle_t, const char *, uint32_t *);
int nvs_set_u8(nvs_handle_t, const char *, uint8_t);
int nvs_set_u32(nvs_handle_t, const char *, uint32_t);
int nvs_commit(nvs_handle_t);
void nvs_close(nvs_handle_t);
""",
    "nvs_flash.h": """#pragma once
int nvs_flash_init_partition(const char *);
""",
    "lwip/inet.h": "#pragma once\n#include <arpa/inet.h>\n",
    "lwip/sockets.h": "#pragma once\n#include <sys/socket.h>\n",
}


class RuntimeTests(unittest.TestCase):
    def test_real_config_upgrades_legacy_presets_and_preserves_saved_calibration(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as work:
            work = pathlib.Path(work)
            for name, source in STUBS.items():
                target = work / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
            binary = work / "config_test"
            compiled = subprocess.run(
                [
                    "cc",
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I",
                    str(work),
                    "-I",
                    str(root / "src"),
                    str(root / "src/config.c"),
                    str(root / "test/config_test.c"),
                    "-o",
                    str(binary),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(
                [str(binary)], check=False, capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Config assertions passed", result.stdout)

    def test_real_controller_drives_four_directions_and_auto_with_bounded_commands(
        self,
    ):
        root = pathlib.Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as work:
            work = pathlib.Path(work)
            for name, source in STUBS.items():
                target = work / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
            binary = work / "runtime_test"
            compiled = subprocess.run(
                [
                    "cc",
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-g",
                    "-I",
                    str(work),
                    "-I",
                    str(root / "src"),
                    *[
                        str(root / "src" / name)
                        for name in [
                            "robot.c",
                            "manual.c",
                            "auto.c",
                            "safety.c",
                            "motor.c",
                            "outputs.c",
                        ]
                    ],
                    str(root / "test/runtime_test.c"),
                    "-o",
                    str(binary),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(
                [str(binary)], check=False, capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Runtime assertions passed", result.stdout)

    def test_transient_http_failures_keep_auto_session_and_retry_exact_ack_and_sample(
        self,
    ):
        root = pathlib.Path(__file__).resolve().parents[1]
        cjson = root / "managed_components/espressif__cjson/cJSON"
        with tempfile.TemporaryDirectory() as work:
            work = pathlib.Path(work)
            for name, source in STUBS.items():
                target = work / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
            binary = work / "device_retry_test"
            compiled = subprocess.run(
                [
                    "cc",
                    "-std=c11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-g",
                    "-DDEVICE_RETRY_TEST",
                    "-I",
                    str(work),
                    "-I",
                    str(root / "src"),
                    "-I",
                    str(cjson),
                    *[
                        str(root / "src" / name)
                        for name in [
                            "robot.c",
                            "manual.c",
                            "auto.c",
                            "safety.c",
                            "motor.c",
                            "outputs.c",
                            "device.c",
                            "protocol.c",
                            "telemetry.c",
                        ]
                    ],
                    str(cjson / "cJSON.c"),
                    str(root / "test/runtime_test.c"),
                    str(root / "test/device_retry_test.c"),
                    "-lm",
                    "-o",
                    str(binary),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(
                [str(binary)], check=False, capture_output=True, text=True, timeout=10
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Device retry assertions passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
