#include "wifi.h"
#include "robot.h"
#include <string.h>
#include <stdatomic.h>
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "nvs_flash.h"

static atomic_bool connected;
static atomic_uint epoch;
static esp_timer_handle_t retry_timer;
static unsigned backoff_ms = 1000;

static void reconnect(void *argument)
{
    (void)argument;
    if (!atomic_load(&connected)) esp_wifi_connect();
}
static void event(void *argument, esp_event_base_t base, int32_t id, void *data)
{
    (void)argument; (void)data;
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) esp_wifi_connect();
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        atomic_store(&connected, false);
        atomic_fetch_add(&epoch, 1);
        robot_link_lost();
        esp_timer_stop(retry_timer);
        esp_timer_start_once(retry_timer, backoff_ms * 1000ULL);
        if (backoff_ms < 30000) backoff_ms = backoff_ms * 2 > 30000 ? 30000 : backoff_ms * 2;
    }
    if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        backoff_ms = 1000;
        atomic_store(&connected, true);
    }
}
bool wifi_connected(void) { return atomic_load(&connected); }
uint32_t wifi_epoch(void) { return atomic_load(&epoch); }

esp_err_t wifi_start(const robot_config_t *config)
{
    esp_err_t e = nvs_flash_init();
    if (e != ESP_OK) return e; // Never silently erase persisted configuration.
    if ((e = esp_netif_init()) != ESP_OK) return e;
    if ((e = esp_event_loop_create_default()) != ESP_OK) return e;
    if (!esp_netif_create_default_wifi_sta()) return ESP_FAIL;
    esp_timer_create_args_t timer = {.callback = reconnect, .name = "wifi_retry"};
    if ((e = esp_timer_create(&timer, &retry_timer)) != ESP_OK) return e;
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    if ((e = esp_wifi_init(&init)) != ESP_OK) return e;
    if ((e = esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, event, NULL)) != ESP_OK) return e;
    if ((e = esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, event, NULL)) != ESP_OK) return e;
    wifi_config_t wifi = {0};
    memcpy(wifi.sta.ssid, config->ssid, strlen(config->ssid));
    memcpy(wifi.sta.password, config->password, strlen(config->password));
    wifi.sta.threshold.authmode = config->password[0] ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;
    if ((e = esp_wifi_set_storage(WIFI_STORAGE_RAM)) != ESP_OK) return e;
    if ((e = esp_wifi_set_mode(WIFI_MODE_STA)) != ESP_OK) return e;
    if ((e = esp_wifi_set_config(WIFI_IF_STA, &wifi)) != ESP_OK) return e;
    esp_sntp_config_t ntp = ESP_NETIF_SNTP_DEFAULT_CONFIG(config->ntp_server);
    if ((e = esp_netif_sntp_init(&ntp)) != ESP_OK) return e;
    if ((e = esp_wifi_set_ps(WIFI_PS_NONE)) != ESP_OK) return e;
    return esp_wifi_start();
}
