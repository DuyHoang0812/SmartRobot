#include "http.h"
#include "wifi.h"
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_timer.h"

#define RESPONSE_CAP 8192
static esp_http_client_handle_t client;
static const robot_config_t *settings;
static char response[RESPONSE_CAP];
static size_t used;
static bool overflow;
static int retry_after;

static esp_err_t on_event(esp_http_client_event_t *event)
{
    if (event->event_id == HTTP_EVENT_ON_DATA && event->data_len > 0) {
        if (used + (size_t)event->data_len >= sizeof(response)) { overflow = true; return ESP_FAIL; }
        memcpy(response + used, event->data, event->data_len);
        used += event->data_len; response[used] = 0;
    }
    if (event->event_id == HTTP_EVENT_ON_HEADER && event->header_key && event->header_value
        && strcasecmp(event->header_key, "Retry-After") == 0) {
        char *end;
        long value = strtol(event->header_value, &end, 10);
        if (!*end && value >= 0 && value <= 300) retry_after = (int)value;
    }
    return ESP_OK;
}

esp_err_t http_init(const robot_config_t *config)
{
    settings = config;
    esp_http_client_config_t c = {.url = config->base_url, .timeout_ms = (int)config->http_timeout_ms,
        .event_handler = on_event, .buffer_size = 2048, .buffer_size_tx = 2048,
        .disable_auto_redirect = true, .max_authorization_retries = -1,
        .keep_alive_enable = true, .skip_cert_common_name_check = false,
        .user_agent = "SmartRobot/6b", .cert_pem = config->ca_pem};
    if (!config->ca_pem) c.crt_bundle_attach = esp_crt_bundle_attach;
    client = esp_http_client_init(&c);
    if (!client) return ESP_FAIL;
    esp_http_client_set_header(client, "X-Device-ID", config->device_id);
    esp_http_client_set_header(client, "X-Device-Secret", config->secret);
    esp_http_client_set_header(client, "Content-Type", "application/json");
    return ESP_OK;
}

void http_close_connection(void) { if (client) esp_http_client_close(client); }

http_result_t http_request(const char *path, const char *body, const char *session, bool authenticating)
{
    http_result_t r = {0};
    char url[384];
    int length = snprintf(url, sizeof(url), "%s%s", settings->base_url, path);
    if (length < 0 || (size_t)length >= sizeof(url) || !client) return r;
    uint32_t epoch = wifi_epoch();
    used = 0; overflow = false; retry_after = 0; response[0] = 0;
    if (esp_http_client_set_url(client, url) != ESP_OK) return r;
    esp_http_client_set_timeout_ms(client, authenticating ? 5000 : (int)settings->http_timeout_ms);
    esp_http_client_set_method(client, body ? HTTP_METHOD_POST : HTTP_METHOD_GET);
    esp_http_client_set_post_field(client, body ? body : "", body ? (int)strlen(body) : 0);
    if (session && session[0]) esp_http_client_set_header(client, "X-Device-Session", session);
    else esp_http_client_delete_header(client, "X-Device-Session");
    r.started_us = esp_timer_get_time();
    esp_err_t e = esp_http_client_perform(client);
    r.finished_us = esp_timer_get_time();
    r.transport_ok = e == ESP_OK && !overflow && wifi_connected() && epoch == wifi_epoch();
    r.status = esp_http_client_get_status_code(client);
    r.retry_after_s = retry_after;
    if (r.transport_ok && used && !memchr(response, 0, used))
        r.json = cJSON_ParseWithLengthOpts(response, used + 1, NULL, true);
    if (!r.transport_ok) http_close_connection();
    return r;
}
