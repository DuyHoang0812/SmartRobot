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
static write_result_t send_ack(const session_t *s, const command_t *c, ack_status_t status)
{
    char *body = protocol_ack_body(c, status);
    if (!body) { robot_fault(true); return WRITE_FAILED; }
    http_result_t r = http_request("/commands/ack", body, s->session_id, false);
    cJSON_free(body);
    bool valid = ok(&r) && protocol_ack_receipt(r.json, s, c, status);
    write_result_t result = protocol_write_result(r.status, r.transport_ok, valid);
    if (result == WRITE_OK && status == ACK_APPLIED
        && cJSON_IsFalse(cJSON_GetObjectItemCaseSensitive(r.json, "duplicate")))
        robot_poll_alive(r.finished_us); // A fresh accepted ACK also proves current control delivery.
    if (result == WRITE_SUPERSEDED) {
        robot_command_conflict();
        ESP_LOGW("device", "ACK superseded (seq=%" PRIu64 "); stopped, fetching current command", c->sequence);
    } else if (result == WRITE_RETRY) {
        ESP_LOGW("device", "ACK retry (seq=%" PRIu64 ", HTTP %d, error=%s, rtt=%lldms); keeping original deadline",
            c->sequence, r.status, esp_err_to_name(r.error), (long long)((r.finished_us-r.started_us)/1000));
    } else if (result == WRITE_FAILED) {
        robot_fault(true);
        ESP_LOGW("device", "ACK failed (HTTP %d, transport=%d, rtt=%lldms)",
            r.status, r.transport_ok, (long long)((r.finished_us-r.started_us)/1000));
    }
    drop_result(&r);
    return result;
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
    command_t pending_ack = {0};
    ack_status_t pending_status = ACK_FAILED;
    uint32_t pending_revision = 0;
    bool have_pending_ack = false;
    char boot[UUID_LEN] = {0};
    char *pending_sample = NULL;
    uint64_t pending_generation = 0, sample_sequence = 0, heartbeat_sequence = 0;
    bool active = false, have_last = false;
    uint32_t epoch = 0, backoff = 500;
    uint32_t telemetry_backoff_ms = 500;
    int64_t heartbeat_at = 0, poll_at = 0, telemetry_at = 0;
    int64_t telemetry_priority_at = 0;
    int64_t command_log_at = 0;
    int64_t idle_log_at = 0;
    command_kind_t logged_kind = KIND_STOP;
    movement_t logged_direction = MOVE_STOP;
    ESP_ERROR_CHECK(http_init(config));
    for (;;) {
        if (robot_hardware_fault()) {
            robot_fault(true);
            vTaskDelay(pdMS_TO_TICKS(30000)); // Latched driver failure requires local repair/reset.
            continue;
        }
        if (!wifi_connected()) {
            if (active) {
                ESP_LOGW("device", "Wi-Fi disconnected; stopping and invalidating device session");
                robot_fault(true); active = false; boot[0] = 0;
            }
            vTaskDelay(pdMS_TO_TICKS(100)); continue;
        }
        if (active && (robot_needs_reset() || epoch != wifi_epoch())) {
            ESP_LOGW("device", "Re-auth required: %s", robot_reset_reason());
            robot_fault(true); active = false; boot[0] = 0;
            http_close_connection();
        }
        if (!active) {
            cJSON_free(pending_sample); pending_sample = NULL;
            have_last = false;
            have_pending_ack = false;
            if (!strncmp(config->base_url, "https://", 8) && time(NULL) < 1704067200) {
                vTaskDelay(pdMS_TO_TICKS(500)); continue; // SNTP first; never bypass TLS date checks.
            }
            if (!boot[0]) boot_uuid(boot);
            char body[128];
            snprintf(body, sizeof(body), "{\"boot_id\":\"%s\",\"firmware_version\":\"6b-15\"}", boot);
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
            ESP_LOGI("device", "Device session established (6b-15); awaiting borrow/control state");
        }
        int64_t now = esp_timer_get_time();
        if (now >= heartbeat_at) {
            if (heartbeat_sequence >= MAX_SEQUENCE) { robot_fault(true); continue; }
            uint64_t attempted = heartbeat_sequence + 1;
            char body[80];
            snprintf(body, sizeof(body), "{\"heartbeat_sequence\":%" PRIu64 "}", attempted);
            http_result_t r = http_request("/heartbeat", body, session.session_id, false);
            int64_t deadline; uint64_t seq, gen;
            bool valid = ok(&r) && protocol_heartbeat(r.json, &session, attempted,
                r.started_us, r.finished_us, &deadline, &seq, &gen);
            if (valid) valid = robot_observe(seq, gen);
            if (valid) {
                robot_heartbeat_alive(deadline);
                heartbeat_sequence = attempted;
                heartbeat_at = r.finished_us + session.heartbeat_ms * 1000LL;
            } else {
                if (protocol_write_result(r.status, r.transport_ok, false) != WRITE_RETRY)
                    robot_fault(true);
                heartbeat_at = r.finished_us + 100000;
                ESP_LOGW("device", "Heartbeat retry (HTTP %d, error=%s); original watchdog unchanged",
                    r.status, esp_err_to_name(r.error));
            }
            drop_result(&r);
            if (robot_needs_reset()) continue;
        }
        if (!heartbeat_sequence) { vTaskDelay(pdMS_TO_TICKS(10)); continue; }
        now = esp_timer_get_time();
        if (now >= poll_at) {
            http_result_t r = http_request("/commands/current", NULL, session.session_id, false);
            envelope_t e;
            bool valid = ok(&r) && protocol_envelope(r.json, &session, r.started_us, r.finished_us, &e);
            if (valid) valid = robot_observe(e.sequence, e.generation);
            if (valid) {
                robot_poll_alive(r.finished_us);
                robot_borrow_update(e.lease_id);
            }
            else {
                if (protocol_write_result(r.status, r.transport_ok, false) != WRITE_RETRY)
                    robot_fault(true);
                ESP_LOGW("device", "Command poll retry (HTTP %d, error=%s); original watchdog unchanged",
                    r.status, esp_err_to_name(r.error));
            }
            poll_at = r.finished_us + session.poll_ms * 1000LL;
            drop_result(&r);
            if (!valid) { vTaskDelay(pdMS_TO_TICKS(10)); continue; }
            if (!e.authorized || e.expired) {
                if (esp_timer_get_time() >= idle_log_at) {
                    ESP_LOGI("device", "Poll OK seq=%" PRIu64 " gen=%" PRIu64 " borrowed=%d authorized=%d pending=%d expired=%d; PWM stopped",
                        e.sequence, e.generation, e.lease_id[0] != 0, e.authorized, e.mode_pending, e.expired);
                    idle_log_at = esp_timer_get_time() + 5000000;
                }
                robot_idle(); have_last = false; have_pending_ack = false;
            } else if (have_last && e.command.sequence == last.sequence) {
                if (!same_command(&e.command, &last)) { robot_fault(true); continue; }
                robot_duplicate_deadline(&e.command); // No apply and no deadline extension on duplicate.
            } else {
                command_t c = e.command;
                if (c.kind != logged_kind || c.direction != logged_direction
                    || esp_timer_get_time() >= command_log_at) {
                    ESP_LOGI("device", "RX seq=%" PRIu64 " gen=%" PRIu64 " kind=%d mode=%s direction=%s ttl=%lldms",
                        c.sequence, c.generation, c.kind, mode_name(c.mode), movement_name(c.direction),
                        (long long)((c.deadline_us - esp_timer_get_time()) / 1000));
                    logged_kind = c.kind; logged_direction = c.direction;
                    command_log_at = esp_timer_get_time() + 1000000;
                }
                uint32_t revision = robot_revision();
                if (revision != robot_revision() || robot_needs_reset()) continue;
                // A lost MODE ACK receipt can be proven by the next authorized MOVE/
                // KEEPALIVE: the backend issues these only AFTER that safe handoff ACK.
                // Require the original pending handoff and its unchanged, unexpired fence.
                if (have_pending_ack && pending_status == ACK_APPLIED && pending_ack.safe_handoff
                    && !e.mode_pending && c.sequence > pending_ack.sequence
                    && c.generation == pending_ack.generation && c.mode == pending_ack.mode
                    && !strcmp(c.lease_id, pending_ack.lease_id)
                    && (c.kind == KIND_MOVE || c.kind == KIND_KEEPALIVE)) {
                    if (!robot_ack_commit(&pending_ack, pending_revision)) { robot_fault(c.mode == MODE_AUTO); continue; }
                    have_pending_ack = false;
                }
                // RECEIVED is optional in v1. Apply/validate then send the final ACK directly,
                // avoiding an extra round-trip racing against 250ms Manual refresh/KEEPALIVE.
                bool retry = have_pending_ack && same_command(&c, &pending_ack);
                ack_status_t accepted = retry ? pending_status : robot_accept(&c);
                if (retry) revision = pending_revision;
                pending_ack = c; pending_status = accepted; pending_revision = revision;
                have_pending_ack = true;
                if (accepted != ACK_APPLIED || c.kind == KIND_MODE || c.kind == KIND_STOP)
                    ESP_LOGI("device", "ACK seq=%" PRIu64 " result=%s", c.sequence, ack_name(accepted));
                write_result_t result = send_ack(&session, &c, accepted);
                if (result != WRITE_OK) {
                    if (result != WRITE_RETRY) have_pending_ack = false;
                    poll_at = 0; vTaskDelay(pdMS_TO_TICKS(10)); continue;
                }
                have_pending_ack = false;
                if (accepted == ACK_APPLIED) {
                    if (!robot_ack_commit(&c, revision)) { robot_fault(c.mode == MODE_AUTO); continue; }
                    last = c; have_last = true;
                } else { robot_fault(true); continue; }
            }
        }
        if (robot_needs_reset()) continue;
        now = esp_timer_get_time();
        // Control polling/ACK has priority over observational telemetry on this one socket.
        if (now >= poll_at && now < telemetry_priority_at) { vTaskDelay(pdMS_TO_TICKS(10)); continue; }
        if (heartbeat_at - now < 800000) { vTaskDelay(pdMS_TO_TICKS(10)); continue; }
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
            telemetry_priority_at = r.finished_us + 1000000;
            bool valid = ok(&r) && protocol_telemetry_receipt(r.json, &session, sample_sequence);
            if (r.transport_ok && r.status == 429) {
                int seconds = r.retry_after_s > 0 ? r.retry_after_s : 1;
                telemetry_at = r.finished_us + seconds * 1000000LL;
            } else {
                write_result_t result = protocol_write_result(r.status, r.transport_ok, valid);
                if (result != WRITE_RETRY) {
                    cJSON_free(pending_sample); pending_sample = NULL;
                }
                uint32_t interval = session.telemetry_ms < 500 ? 500 : session.telemetry_ms;
                telemetry_at = r.finished_us + interval * 1000LL;
                if (result == WRITE_SUPERSEDED) { poll_at = 0; }
                else if (result == WRITE_RETRY) {
                    // Retain body/counter after an uncertain write: backend retries are idempotent.
                    telemetry_at = r.finished_us + telemetry_backoff_ms * 1000LL;
                    if (telemetry_backoff_ms < 2000) telemetry_backoff_ms *= 2;
                    ESP_LOGW("device", "Telemetry deferred (HTTP %d, error=%s); control session retained",
                        r.status, esp_err_to_name(r.error));
                }
                else if (result == WRITE_FAILED) {
                    robot_fault(true);
                    ESP_LOGW("device", "Telemetry failed (HTTP %d, transport=%d)", r.status, r.transport_ok);
                }
                else telemetry_backoff_ms = 500;
            }
            drop_result(&r);
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
