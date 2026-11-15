#include "protocol.h"
#include <ctype.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

const char *mode_name(robot_mode_t v) { return v == MODE_AUTO ? "AUTO" : "MANUAL"; }
const char *movement_name(movement_t v)
{
    static const char *names[] = {"STOPPED", "FORWARD", "BACKWARD", "TURN_LEFT", "TURN_RIGHT"};
    return v >= MOVE_STOP && v <= MOVE_RIGHT ? names[v] : "STOPPED";
}
const char *obstacle_name(obstacle_t v)
{
    static const char *names[] = {"CLEAR", "BLOCKED", "SENSOR_ERROR"};
    return v >= OBS_CLEAR && v <= OBS_SENSOR_ERROR ? names[v] : "SENSOR_ERROR";
}
const char *ack_name(ack_status_t v)
{
    static const char *names[] = {"RECEIVED", "APPLIED", "REJECTED", "FAILED"};
    return v >= ACK_RECEIVED && v <= ACK_FAILED ? names[v] : "FAILED";
}
static const char *str(const cJSON *j, const char *key)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(j, key);
    return cJSON_IsString(v) ? v->valuestring : NULL;
}
static bool eq(const cJSON *j, const char *key, const char *value)
{
    const char *s = str(j, key); return s && strcmp(s, value) == 0;
}
static bool boolean(const cJSON *j, const char *key, bool *value)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(j, key);
    if (!cJSON_IsBool(v)) return false;
    *value = cJSON_IsTrue(v); return true;
}
bool protocol_uuid(const char *s)
{
    if (!s || strlen(s) != 36) return false;
    for (int i = 0; i < 36; ++i) {
        if (i == 8 || i == 13 || i == 18 || i == 23) { if (s[i] != '-') return false; }
        else if (!isxdigit((unsigned char)s[i])) return false;
    }
    return true;
}
bool protocol_uint(const cJSON *j, const char *key, uint64_t *value)
{
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(j, key);
    if (!cJSON_IsNumber(v) || !isfinite(v->valuedouble) || v->valuedouble < 0
        || v->valuedouble > (double)MAX_SEQUENCE || floor(v->valuedouble) != v->valuedouble) return false;
    *value = (uint64_t)v->valuedouble; return true;
}
static bool id(const cJSON *j, const char *key, char *dst)
{
    const char *s = str(j, key);
    if (!protocol_uuid(s)) return false;
    memcpy(dst, s, UUID_LEN); return true;
}
static bool mode(const cJSON *j, const char *key, robot_mode_t *v)
{
    if (eq(j, key, "MANUAL")) *v = MODE_MANUAL;
    else if (eq(j, key, "AUTO")) *v = MODE_AUTO;
    else return false;
    return true;
}
bool protocol_time(const char *s, int64_t *microseconds)
{
    if (!s || strlen(s) < 20 || s[4] != '-' || s[7] != '-' || s[10] != 'T'
        || s[13] != ':' || s[16] != ':') return false;
    int y, m, d, h, minute, second;
    if (sscanf(s, "%4d-%2d-%2dT%2d:%2d:%2d", &y, &m, &d, &h, &minute, &second) != 6
        || y < 2020 || y > 2100 || m < 1 || m > 12 || h > 23 || minute > 59 || second > 59
        || h < 0 || minute < 0 || second < 0) return false;
    const int days_month[] = {31,28,31,30,31,30,31,31,30,31,30,31};
    bool leap = y % 4 == 0 && (y % 100 != 0 || y % 400 == 0);
    if (d < 1 || d > days_month[m-1] + (m == 2 && leap)) return false;
    for (int i = 0; i < 19; ++i)
        if (i != 4 && i != 7 && i != 10 && i != 13 && i != 16 && !isdigit((unsigned char)s[i])) return false;
    const char *end = s + 19;
    int64_t fraction = 0;
    if (*end == '.') {
        ++end; int digits = 0;
        while (isdigit((unsigned char)*end) && digits < 6) { fraction = fraction * 10 + (*end++ - '0'); ++digits; }
        if (!digits || isdigit((unsigned char)*end)) return false;
        for (; digits < 6; ++digits) fraction *= 10;
    }
    if (strcmp(end, "Z") && strcmp(end, "+00:00")) return false;
    // Civil date -> Unix days, independent of SNTP/timezone or 32-bit time_t.
    y -= m <= 2;
    int era = y / 400, yoe = y - era * 400;
    int doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    int doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    int64_t days = era * 146097LL + doe - 719468;
    *microseconds = ((days * 24 + h) * 3600 + minute * 60 + second) * 1000000 + fraction;
    return true;
}
static bool timestamp(const cJSON *j, const char *key, int64_t *us)
{
    return protocol_time(str(j, key), us);
}
static bool interval(const cJSON *j, const char *key, uint32_t *dst, unsigned min, unsigned max)
{
    uint64_t v;
    if (!protocol_uint(j, key, &v) || v < min || v > max) return false;
    *dst = (uint32_t)v; return true;
}
bool protocol_auth(const cJSON *j, session_t *s)
{
    uint64_t version; int64_t now;
    return cJSON_IsObject(j) && protocol_uint(j, "protocol_version", &version) && version == 1
        && id(j, "robot_id", s->robot_id) && id(j, "device_session_id", s->session_id)
        && protocol_uint(j, "sequence", &s->sequence) && protocol_uint(j, "generation", &s->generation)
        && s->generation <= INT32_MAX && timestamp(j, "server_time", &now)
        && interval(j, "heartbeat_interval_ms", &s->heartbeat_ms, 50, 10000)
        && interval(j, "offline_timeout_ms", &s->offline_ms, 1000, 300000)
        && s->heartbeat_ms < s->offline_ms
        && interval(j, "poll_interval_ms", &s->poll_ms, 50, 200)
        && interval(j, "telemetry_min_interval_ms", &s->telemetry_ms, 100, 5000)
        && interval(j, "manual_command_ttl_ms", &s->manual_ttl_ms, 300, 1500)
        && interval(j, "mode_command_ttl_ms", &s->mode_ttl_ms, 2000, 5000);
}

bool protocol_envelope(const cJSON *j, const session_t *s, int64_t start, int64_t received, envelope_t *e)
{
    memset(e, 0, sizeof(*e));
    robot_mode_t requested;
    int64_t server, authorization, expiry, lease, issued;
    if (!eq(j, "robot_id", s->robot_id) || !eq(j, "device_session_id", s->session_id)
        || !eq(j, "fail_safe", "STOP") || !timestamp(j, "server_time", &server)
        || !protocol_uint(j, "sequence", &e->sequence) || !protocol_uint(j, "generation", &e->generation)
        || e->generation > INT32_MAX || !mode(j, "requested_mode", &requested)
        || !boolean(j, "control_authorized", &e->authorized) || !boolean(j, "mode_pending", &e->mode_pending)
        || received < start) return false;
    const cJSON *c = cJSON_GetObjectItemCaseSensitive(j, "command");
    if (!e->authorized) return cJSON_IsNull(c) && cJSON_IsNull(cJSON_GetObjectItemCaseSensitive(j, "authorization_expires_at"));
    command_t *out = &e->command;
    if (!cJSON_IsObject(c) || !id(c, "command_id", out->id) || !id(c, "robot_id", out->robot_id)
        || strcmp(out->robot_id, s->robot_id) || !id(c, "control_session_id", out->lease_id)
        || !protocol_uint(c, "sequence", &out->sequence) || out->sequence != e->sequence || !out->sequence
        || !protocol_uint(c, "generation", &out->generation) || out->generation != e->generation
        || !mode(c, "mode", &out->mode) || out->mode != requested
        || !timestamp(j, "authorization_expires_at", &authorization) || !timestamp(j, "lease_expires_at", &lease)
        || !timestamp(c, "issued_at", &issued) || !timestamp(c, "expires_at", &expiry)
        || expiry <= issued || authorization > expiry || authorization > lease
        || authorization <= server || issued > server) return false;
    if (!(eq(c, "status", "ACCEPTED") || eq(c, "status", "RECEIVED")
          || eq(c, "status", "APPLIED") || eq(c, "status", "EXECUTED"))) return false;
    if (eq(c, "kind", "MOVE")) out->kind = KIND_MOVE;
    else if (eq(c, "kind", "STOP")) out->kind = KIND_STOP;
    else if (eq(c, "kind", "MODE")) out->kind = KIND_MODE;
    else if (eq(c, "kind", "KEEPALIVE")) out->kind = KIND_KEEPALIVE;
    else return false;
    if (eq(c, "direction", "STOP")) out->direction = MOVE_STOP;
    else if (eq(c, "direction", "FORWARD")) out->direction = MOVE_FORWARD;
    else if (eq(c, "direction", "BACKWARD")) out->direction = MOVE_BACKWARD;
    else if (eq(c, "direction", "TURN_LEFT")) out->direction = MOVE_LEFT;
    else if (eq(c, "direction", "TURN_RIGHT")) out->direction = MOVE_RIGHT;
    else return false;
    if ((out->kind == KIND_MOVE && (out->direction == MOVE_STOP || out->mode != MODE_MANUAL || e->mode_pending))
        || (out->kind == KIND_STOP && out->mode != MODE_MANUAL)
        || (out->kind != KIND_MOVE && out->direction != MOVE_STOP)
        || (out->kind == KIND_KEEPALIVE && (out->mode != MODE_AUTO || e->mode_pending))) return false;
    uint32_t ttl = out->kind == KIND_MOVE || out->kind == KIND_STOP ? s->manual_ttl_ms : s->mode_ttl_ms;
    if (expiry - issued > ttl * 1000LL) return false;
    int64_t remaining = authorization - server;
    if (remaining > ttl * 1000LL) remaining = ttl * 1000LL;
    out->deadline_us = start + remaining - 20000; // Full RTT + 20ms margin, not receive + TTL.
    out->safe_handoff = out->kind == KIND_MODE || (out->kind == KIND_STOP && e->mode_pending);
    return out->deadline_us > received;
}

bool protocol_heartbeat(const cJSON *j, const session_t *s, uint64_t sequence, int64_t start,
                        int64_t received, int64_t *deadline, uint64_t *server_seq, uint64_t *server_gen)
{
    uint64_t counter; int64_t server, seen;
    if (!eq(j, "robot_id", s->robot_id) || !eq(j, "device_session_id", s->session_id)
        || !protocol_uint(j, "heartbeat_sequence", &counter) || counter != sequence
        || !protocol_uint(j, "sequence", server_seq) || !protocol_uint(j, "generation", server_gen)
        || !timestamp(j, "server_time", &server) || !timestamp(j, "last_seen_at", &seen)
        || seen > server || received < start) return false;
    *deadline = start + seen + s->offline_ms * 1000LL - server - 20000;
    return *deadline > received;
}

bool protocol_ack_receipt(const cJSON *j, const session_t *s, const command_t *c, ack_status_t status)
{
    uint64_t seq; int64_t at; bool duplicate;
    return eq(j, "robot_id", s->robot_id) && eq(j, "command_id", c->id)
        && eq(j, "status", ack_name(status)) && protocol_uint(j, "sequence", &seq) && seq == c->sequence
        && timestamp(j, "acknowledged_at", &at) && boolean(j, "duplicate", &duplicate);
}
bool protocol_telemetry_receipt(const cJSON *j, const session_t *s, uint64_t sample)
{
    uint64_t seq; int64_t at; bool duplicate;
    return eq(j, "robot_id", s->robot_id) && protocol_uint(j, "sample_sequence", &seq) && seq == sample
        && timestamp(j, "recorded_at", &at) && boolean(j, "duplicate", &duplicate);
}
char *protocol_ack_body(const command_t *c, ack_status_t status)
{
    cJSON *j = cJSON_CreateObject();
    if (!j) return NULL;
    cJSON_AddStringToObject(j, "command_id", c->id);
    cJSON_AddNumberToObject(j, "sequence", (double)c->sequence);
    cJSON_AddNumberToObject(j, "generation", (double)c->generation);
    cJSON_AddStringToObject(j, "status", ack_name(status));
    bool safe = c->safe_handoff && status == ACK_APPLIED;
    cJSON_AddBoolToObject(j, "safe_mode_switch", safe);
    if (safe) {
        cJSON_AddStringToObject(j, "actual_mode", mode_name(c->mode));
        cJSON_AddStringToObject(j, "actual_movement", "STOPPED");
    }
    char *body = cJSON_PrintUnformatted(j); cJSON_Delete(j); return body;
}
