#pragma once
#include "config.h"
#include "cJSON.h"

typedef struct {
    int status, retry_after_s;
    int64_t started_us, finished_us;
    cJSON *json;
    bool transport_ok;
    esp_err_t error;
} http_result_t;
esp_err_t http_init(const robot_config_t *config);
http_result_t http_request(const char *path, const char *body, const char *session, bool authenticating);
void http_close_connection(void);
