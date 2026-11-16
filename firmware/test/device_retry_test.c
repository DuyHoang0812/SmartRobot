// Runs the real device/controller/protocol modules against scripted HTTP responses.
// No socket, GPIO or physical robot is exercised by this host test.
#include "http.h"
#include "protocol.h"
#include "robot.h"
#include "esp_timer.h"
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>

void device_task(void *config);
void test_delay(int ms);
void test_network_setup(const robot_config_t *config);
int runtime_suite_main(void);
static jmp_buf finished;
static const char *rid = "22222222-2222-4222-8222-222222222222";
static const char *sid = "33333333-3333-4333-8333-333333333333";
static const char *cid = "44444444-4444-4444-8444-444444444444";
static const char *lid = "55555555-5555-4555-8555-555555555555";
static int authenticates, mode_acks, heartbeat_failures, telemetry_calls, requests;
static bool mode_confirmed, poll_failed;
static uint64_t sequence = 1, failed_heartbeat;
static int64_t issued, started;
static char mode_ack_body[512], sample_body[1024];

bool wifi_connected(void) { return true; }
uint32_t wifi_epoch(void) { return 1; }
esp_err_t http_init(const robot_config_t *config) { (void)config; return ESP_OK; }
void http_close_connection(void) {}
static void stamp(cJSON *json, const char *key, int64_t at)
{
    char value[64];
    snprintf(value, sizeof(value), "2026-11-15T16:00:%02d.%06dZ", (int)(at/1000000), (int)(at%1000000));
    cJSON_AddStringToObject(json, key, value);
}
static cJSON *base(void)
{
    cJSON *j = cJSON_CreateObject(); assert(j);
    cJSON_AddStringToObject(j, "robot_id", rid);
    cJSON_AddStringToObject(j, "device_session_id", sid);
    stamp(j, "server_time", esp_timer_get_time());
    cJSON_AddNumberToObject(j, "sequence", (double)sequence);
    cJSON_AddNumberToObject(j, "generation", 1);
    return j;
}
static void fail_transport(http_result_t *r)
{
    test_delay(260); r->finished_us = esp_timer_get_time();
    r->transport_ok = false; r->status = -1; r->error = ESP_ERR_INVALID_STATE;
}
http_result_t http_request(const char *path, const char *body, const char *session, bool authenticating)
{
    (void)session; (void)authenticating;
    assert(++requests < 1000);
    http_result_t r = {.status = 200, .transport_ok = true, .started_us = esp_timer_get_time()};
    if (!strcmp(path, "/authenticate")) {
        assert(++authenticates == 1); test_delay(30);
        r.json = base();
        cJSON_ReplaceItemInObject(r.json, "sequence", cJSON_CreateNumber(0));
        cJSON_AddNumberToObject(r.json, "protocol_version", 1);
        cJSON_AddNumberToObject(r.json, "heartbeat_interval_ms", 2000);
        cJSON_AddNumberToObject(r.json, "offline_timeout_ms", 15000);
        cJSON_AddNumberToObject(r.json, "poll_interval_ms", 100);
        cJSON_AddNumberToObject(r.json, "telemetry_min_interval_ms", 200);
        cJSON_AddNumberToObject(r.json, "manual_command_ttl_ms", 700);
        cJSON_AddNumberToObject(r.json, "mode_command_ttl_ms", 3000);
    } else if (!strcmp(path, "/heartbeat")) {
        cJSON *payload = cJSON_Parse(body); uint64_t counter;
        assert(protocol_uint(payload, "heartbeat_sequence", &counter)); cJSON_Delete(payload);
        if (failed_heartbeat) { assert(counter == failed_heartbeat); failed_heartbeat = 0; }
        else if (heartbeat_failures == 0 || (mode_confirmed && heartbeat_failures == 1)) {
            ++heartbeat_failures; failed_heartbeat = counter; fail_transport(&r); return r;
        }
        test_delay(260); r.json = base();
        cJSON_AddNumberToObject(r.json, "heartbeat_sequence", (double)counter);
        stamp(r.json, "last_seen_at", esp_timer_get_time());
    } else if (!strcmp(path, "/commands/current")) {
        if (telemetry_calls && !poll_failed) { poll_failed = true; fail_transport(&r); return r; }
        if (esp_timer_get_time() - started >= 8000000 && telemetry_calls >= 3) {
            robot_snapshot_t snapshot; robot_snapshot(&snapshot);
            assert(authenticates == 1 && mode_acks == 2 && heartbeat_failures == 2 && poll_failed);
            assert(snapshot.mode == MODE_AUTO && !snapshot.needs_reset && snapshot.authorized);
            assert(snapshot.movement == MOVE_FORWARD && snapshot.relay && snapshot.motor_duty == 75);
            assert(snapshot.left_motor_percent == 100 && snapshot.right_motor_percent == 83.5f);
            assert(snapshot.left_motor_duty == 75 && snapshot.right_motor_duty == 63);
            longjmp(finished, 1);
        }
        test_delay(260);
        if (!issued || (mode_confirmed && esp_timer_get_time() - issued >= 1000000)) {
            if (issued) ++sequence;
            issued = esp_timer_get_time();
        }
        r.json = base();
        cJSON_AddStringToObject(r.json, "requested_mode", "AUTO");
        cJSON_AddBoolToObject(r.json, "mode_pending", !mode_confirmed);
        cJSON_AddBoolToObject(r.json, "control_authorized", true);
        cJSON_AddStringToObject(r.json, "control_session_id", lid);
        cJSON_AddNullToObject(r.json, "lease_expires_at");
        stamp(r.json, "authorization_expires_at", issued + 3000000);
        cJSON_AddStringToObject(r.json, "fail_safe", "STOP");
        cJSON *c = cJSON_AddObjectToObject(r.json, "command");
        cJSON_AddStringToObject(c, "command_id", cid);
        cJSON_AddStringToObject(c, "robot_id", rid);
        cJSON_AddStringToObject(c, "control_session_id", lid);
        cJSON_AddNumberToObject(c, "sequence", (double)sequence);
        cJSON_AddNumberToObject(c, "generation", 1);
        cJSON_AddStringToObject(c, "kind", sequence == 1 ? "MODE" : "KEEPALIVE");
        cJSON_AddStringToObject(c, "mode", "AUTO");
        cJSON_AddStringToObject(c, "direction", "STOP");
        cJSON_AddStringToObject(c, "status", "ACCEPTED");
        stamp(c, "issued_at", issued); stamp(c, "expires_at", issued + 3000000);
    } else if (!strcmp(path, "/commands/ack")) {
        cJSON *payload = cJSON_Parse(body); uint64_t counter;
        assert(protocol_uint(payload, "sequence", &counter));
        if (strcmp(cJSON_GetObjectItemCaseSensitive(payload, "status")->valuestring, "APPLIED")) {
            robot_snapshot_t snapshot; robot_snapshot(&snapshot);
            fprintf(stderr, "Unexpected ACK at %lldus: %s mode=%d reset=%d reason=%s\n",
                (long long)esp_timer_get_time(), body, snapshot.mode, snapshot.needs_reset, robot_reset_reason());
        }
        assert(!strcmp(cJSON_GetObjectItemCaseSensitive(payload, "status")->valuestring, "APPLIED"));
        cJSON_Delete(payload);
        if (counter == 1) {
            if (!mode_acks) snprintf(mode_ack_body, sizeof(mode_ack_body), "%s", body);
            assert(!strcmp(mode_ack_body, body));
            mode_confirmed = true; // Server persisted APPLIED but both receipts are lost.
            if (++mode_acks <= 2) { fail_transport(&r); return r; }
        }
        test_delay(260); r.json = base();
        cJSON_AddStringToObject(r.json, "command_id", cid);
        cJSON_ReplaceItemInObject(r.json, "sequence", cJSON_CreateNumber((double)counter));
        cJSON_AddStringToObject(r.json, "status", "APPLIED");
        stamp(r.json, "acknowledged_at", esp_timer_get_time());
        cJSON_AddBoolToObject(r.json, "duplicate", counter == 1);
    } else if (!strcmp(path, "/telemetry")) {
        ++telemetry_calls;
        if (telemetry_calls == 1) snprintf(sample_body, sizeof(sample_body), "%s", body);
        if (telemetry_calls <= 3) assert(!strcmp(sample_body, body));
        if (telemetry_calls < 3) { fail_transport(&r); return r; }
        cJSON *payload = cJSON_Parse(body); uint64_t counter;
        assert(protocol_uint(payload, "sample_sequence", &counter)); cJSON_Delete(payload);
        test_delay(260); r.json = base();
        cJSON_AddNumberToObject(r.json, "sample_sequence", (double)counter);
        stamp(r.json, "recorded_at", esp_timer_get_time());
        cJSON_AddBoolToObject(r.json, "duplicate", false);
    } else assert(false);
    r.finished_us = esp_timer_get_time(); return r;
}
int main(void)
{
    assert(runtime_suite_main() == 0);
    robot_config_t config = {.motors_enabled = true, .full_speed = 75, .slow_speed = 30, .turn_speed = 75};
    test_network_setup(&config); started = esp_timer_get_time();
    if (!setjmp(finished)) device_task(&config);
    puts("Device retry assertions passed: repeated 260ms failures, exact ACK/sample retries, one session, Auto and motor power retained");
    return 0;
}
