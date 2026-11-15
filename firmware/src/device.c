#include "http.h"
#include "protocol.h"
#include "robot.h"
#include "wifi.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "esp_log.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static void boot_uuid(char out[UUID_LEN])
{
    uint8_t b[16]; esp_fill_random(b, sizeof(b));
    b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
    snprintf(out, UUID_LEN, "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
        b[0],b[1],b[2],b[3],b[4],b[5],b[6],b[7],b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]);
}
static void drop_result(http_result_t *r) { cJSON_Delete(r->json); r->json = NULL; }
static bool ok(const http_result_t *r) { return r->transport_ok && r->status == 200 && cJSON_IsObject(r->json); }
static bool send_ack(const session_t *s, const command_t *c, ack_status_t status)
{
    char *body = protocol_ack_body(c, status);
    if (!body) { robot_fault(true); return false; }
    http_result_t r = http_request("/commands/ack", body, s->session_id, false);
    cJSON_free(body);
    bool valid = ok(&r) && protocol_ack_receipt(r.json, s, c, status);
    if (!valid) robot_fault(!r.transport_ok || r.status != 409 || c->mode == MODE_AUTO);
    drop_result(&r);
    return valid;
}

static bool same_command(const command_t *a, const command_t *b)
{
    return a->sequence == b->sequence && a->generation == b->generation
        && a->mode == b->mode && a->kind == b->kind && a->direction == b->direction
        && !strcmp(a->id, b->id) && !strcmp(a->lease_id, b->lease_id);
}

void device_task(void *argument)
{
    const robot_config_t *config = argument;
    session_t session = {0};
    command_t last = {0};
    char boot[UUID_LEN] = {0};
    char *pending_sample = NULL;
    uint64_t pending_generation = 0, sample_sequence = 0, heartbeat_sequence = 0;
    bool active = false, have_last = false;
    uint32_t epoch = 0, backoff = 500;
    int64_t heartbeat_at = 0, poll_at = 0, telemetry_at = 0;
    ESP_ERROR_CHECK(http_init(config));
    for (;;) {
        if (robot_hardware_fault()) {
            robot_fault(true);
            vTaskDelay(pdMS_TO_TICKS(30000)); // Latched driver failure requires local repair/reset.
            continue;
        }
        if (!wifi_connected()) {
            if (active) { robot_fault(true); active = false; boot[0] = 0; }
            vTaskDelay(pdMS_TO_TICKS(100)); continue;
        }
        if (active && (robot_needs_reset() || epoch != wifi_epoch())) {
            robot_fault(true); active = false; boot[0] = 0;
            http_close_connection();
        }
        if (!active) {
            cJSON_free(pending_sample); pending_sample = NULL;
            have_last = false;
            if (!strncmp(config->base_url, "https://", 8) && time(NULL) < 1704067200) {
                vTaskDelay(pdMS_TO_TICKS(500)); continue; // SNTP first; never bypass TLS date checks.
            }
            if (!boot[0]) boot_uuid(boot);
            char body[128];
            snprintf(body, sizeof(body), "{\"boot_id\":\"%s\",\"firmware_version\":\"6b-1\"}", boot);
            http_result_t r = http_request("/authenticate", body, NULL, true);
            bool valid = ok(&r) && protocol_auth(r.json, &session);
            int status = r.status;
            drop_result(&r);
            if (!valid) {
                robot_fault(true);
                if (status == 409) boot[0] = 0;
                unsigned wait = status == 401 || status == 403 || status == 422 ? 30000 : backoff;
                ESP_LOGW("device", "Authentication unavailable (HTTP %d); outputs remain stopped", status);
                vTaskDelay(pdMS_TO_TICKS(wait));
                if (backoff < 5000) backoff = backoff * 2 > 5000 ? 5000 : backoff * 2;
                continue; // Keep the same boot UUID after a lost authenticate response.
            }
            epoch = wifi_epoch();
            robot_new_session(session.sequence, session.generation);
            heartbeat_sequence = sample_sequence = 0;
            heartbeat_at = poll_at = telemetry_at = 0;
            active = true; backoff = 500;
            ESP_LOGI("device", "Device session established; awaiting control authorization");
        }
        int64_t now = esp_timer_get_time();
        if (now >= heartbeat_at) {
            if (++heartbeat_sequence > MAX_SEQUENCE) { robot_fault(true); continue; }
            char body[80];
            snprintf(body, sizeof(body), "{\"heartbeat_sequence\":%" PRIu64 "}", heartbeat_sequence);
            http_result_t r = http_request("/heartbeat", body, session.session_id, false);
            int64_t deadline; uint64_t seq, gen;
            bool valid = ok(&r) && protocol_heartbeat(r.json, &session, heartbeat_sequence,
                r.started_us, r.finished_us, &deadline, &seq, &gen);
            if (valid) valid = robot_observe(seq, gen);
            if (valid) {
                robot_heartbeat_alive(deadline);
                heartbeat_at = r.finished_us + session.heartbeat_ms * 1000LL;
            } else robot_fault(true);
            drop_result(&r);
            if (!valid) { vTaskDelay(pdMS_TO_TICKS(500)); continue; }
        }
        now = esp_timer_get_time();
        if (now >= poll_at) {
            http_result_t r = http_request("/commands/current", NULL, session.session_id, false);
            envelope_t e;
            bool valid = ok(&r) && protocol_envelope(r.json, &session, r.started_us, r.finished_us, &e);
            if (valid) valid = robot_observe(e.sequence, e.generation);
            if (valid) robot_poll_alive(r.finished_us);
            else robot_fault(true);
            poll_at = r.finished_us + session.poll_ms * 1000LL;
            drop_result(&r);
            if (!valid) { vTaskDelay(pdMS_TO_TICKS(500)); continue; }
            if (!e.authorized) {
                robot_idle(); have_last = false;
            } else if (have_last && e.command.sequence == last.sequence) {
                if (!same_command(&e.command, &last)) { robot_fault(true); continue; }
                robot_duplicate_deadline(&e.command); // No apply and no deadline extension on duplicate.
            } else {
                command_t c = e.command;
                uint32_t revision = robot_revision();
                if (!send_ack(&session, &c, ACK_RECEIVED)) continue;
                if (revision != robot_revision() || robot_needs_reset()) continue;
                ack_status_t accepted = robot_accept(&c);
                if (!send_ack(&session, &c, accepted)) continue;
                if (accepted == ACK_APPLIED) {
                    if (!robot_ack_commit(&c, revision)) { robot_fault(c.mode == MODE_AUTO); continue; }
                    last = c; have_last = true;
                } else { robot_fault(true); continue; }
            }
        }
        if (robot_needs_reset()) continue;
        now = esp_timer_get_time();
        if (now >= telemetry_at) {
            robot_snapshot_t state; robot_snapshot(&state);
            if (pending_sample && pending_generation != state.generation) {
                cJSON_free(pending_sample); pending_sample = NULL;
            }
            if (!pending_sample) {
                if (++sample_sequence > MAX_SEQUENCE) { robot_fault(true); continue; }
                pending_sample = telemetry_body(&session, &state, sample_sequence, now);
                pending_generation = state.generation;
            }
            if (!pending_sample) { robot_fault(true); continue; }
            http_result_t r = http_request("/telemetry", pending_sample, session.session_id, false);
            bool valid = ok(&r) && protocol_telemetry_receipt(r.json, &session, sample_sequence);
            if (r.transport_ok && r.status == 429) {
                int seconds = r.retry_after_s > 0 ? r.retry_after_s : 1;
                telemetry_at = r.finished_us + seconds * 1000000LL;
            } else {
                cJSON_free(pending_sample); pending_sample = NULL;
                telemetry_at = r.finished_us + session.telemetry_ms * 1000LL;
                if (!valid) robot_fault(!r.transport_ok || r.status != 409 || state.mode == MODE_AUTO);
            }
            drop_result(&r);
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
