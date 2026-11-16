// Pure wire-format/deadline unit tests, NOT a robot/hardware/network simulator.
#include "protocol.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static const char *robot = "22222222-2222-4222-8222-222222222222";
static const char *sid = "33333333-3333-4333-8333-333333333333";
static const char *cid = "44444444-4444-4444-8444-444444444444";
static const char *lid = "55555555-5555-4555-8555-555555555555";

static cJSON *envelope(void)
{
    cJSON *j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "robot_id", robot);
    cJSON_AddStringToObject(j, "device_session_id", sid);
    cJSON_AddStringToObject(j, "control_session_id", lid);
    cJSON_AddStringToObject(j, "server_time", "2026-11-15T16:00:02.100Z");
    cJSON_AddNumberToObject(j, "sequence", 2);
    cJSON_AddNumberToObject(j, "generation", 3);
    cJSON_AddStringToObject(j, "requested_mode", "MANUAL");
    cJSON_AddBoolToObject(j, "mode_pending", false);
    cJSON_AddBoolToObject(j, "control_authorized", true);
    cJSON_AddStringToObject(j, "authorization_expires_at", "2026-11-15T16:00:02.700Z");
    cJSON_AddStringToObject(j, "lease_expires_at", "2026-11-15T16:00:12Z");
    cJSON_AddStringToObject(j, "fail_safe", "STOP");
    cJSON *c = cJSON_AddObjectToObject(j, "command");
    cJSON_AddStringToObject(c, "command_id", cid);
    cJSON_AddStringToObject(c, "robot_id", robot);
    cJSON_AddStringToObject(c, "control_session_id", lid);
    cJSON_AddNumberToObject(c, "sequence", 2);
    cJSON_AddNumberToObject(c, "generation", 3);
    cJSON_AddStringToObject(c, "mode", "MANUAL");
    cJSON_AddStringToObject(c, "kind", "MOVE");
    cJSON_AddStringToObject(c, "direction", "FORWARD");
    cJSON_AddStringToObject(c, "issued_at", "2026-11-15T16:00:02Z");
    cJSON_AddStringToObject(c, "expires_at", "2026-11-15T16:00:02.700Z");
    cJSON_AddStringToObject(c, "status", "ACCEPTED");
    return j;
}

int main(int argc, char **argv)
{
    int64_t us, other;
    assert(protocol_time("2026-11-15T16:00:02.123456Z", &us));
    assert(protocol_time("2026-11-15T16:00:02.123456+00:00", &other) && us == other);
    assert(protocol_time("2026-11-15T16:00:02Z", &other) && us - other == 123456);
    assert(!protocol_time("2026-02-29T00:00:00Z", &us));
    assert(protocol_time("2028-02-29T00:00:00Z", &us));
    assert(!protocol_time("2026-11-15T24:00:00Z", &us));
    assert(!protocol_time("2026-11-15T16:00:02+07:00", &us));
    assert(!protocol_time("2026-11-15T16:00:02.1234567Z", &us));
    assert(!protocol_time(NULL, &us));
    assert(protocol_uuid(robot)); assert(!protocol_uuid("not-a-uuid"));
    session_t s = {.manual_ttl_ms = 700, .mode_ttl_ms = 3000};
    strcpy(s.robot_id, robot); strcpy(s.session_id, sid);
    cJSON *j = envelope(); envelope_t e;
    assert(protocol_envelope(j, &s, 1000000, 1100000, &e));
    assert(!strcmp(e.lease_id, lid));
    assert(e.command.deadline_us == 1580000); // 600ms remaining minus RTT and 20ms margin.
    cJSON_ReplaceItemInObject(j, "lease_expires_at", cJSON_CreateNull());
    assert(protocol_envelope(j, &s, 1000000, 1100000, &e));
    assert(e.command.deadline_us == 1580000); // Persistent borrow still has bounded actuation.
    cJSON_DeleteItemFromObject(j, "lease_expires_at");
    assert(!protocol_envelope(j, &s, 1000000, 1100000, &e));
    cJSON_AddStringToObject(j, "lease_expires_at", "2026-11-15T16:00:12Z");
    assert(protocol_envelope(j, &s, 1000000, 1600000, &e) && e.expired);
    assert(protocol_write_result(409, true, false) == WRITE_SUPERSEDED);
    assert(protocol_write_result(409, false, false) == WRITE_RETRY);
    assert(protocol_write_result(200, true, true) == WRITE_OK);
    assert(protocol_write_result(200, true, false) == WRITE_FAILED);
    assert(protocol_write_result(401, true, false) == WRITE_FAILED);
    assert(protocol_write_result(500, true, false) == WRITE_RETRY);
    assert(protocol_write_result(-1, false, false) == WRITE_RETRY);
    assert(protocol_write_result(408, true, false) == WRITE_RETRY);
    assert(protocol_write_result(429, true, false) == WRITE_RETRY);
    const char *directions[] = {"FORWARD", "BACKWARD", "TURN_LEFT", "TURN_RIGHT"};
    for (int n = 0; n < 4; ++n) {
        cJSON *cmd = cJSON_GetObjectItemCaseSensitive(j, "command");
        cJSON_ReplaceItemInObject(cmd, "direction", cJSON_CreateString(directions[n]));
        assert(protocol_envelope(j, &s, 1000000, 1100000, &e));
        assert(e.command.direction == (movement_t)(MOVE_FORWARD + n));
    }
    uint64_t number;
    cJSON_ReplaceItemInObject(j, "sequence", cJSON_CreateNumber(2.5));
    assert(!protocol_uint(j, "sequence", &number));
    cJSON_ReplaceItemInObject(j, "sequence", cJSON_CreateNumber(-1));
    assert(!protocol_uint(j, "sequence", &number));
    cJSON_ReplaceItemInObject(j, "sequence", cJSON_CreateNumber(9007199254740992.0));
    assert(!protocol_uint(j, "sequence", &number));
    cJSON_Delete(j); j = envelope();
    cJSON_ReplaceItemInObject(cJSON_GetObjectItemCaseSensitive(j, "command"), "status", cJSON_CreateString("SUPERSEDED"));
    assert(!protocol_envelope(j, &s, 1000000, 1100000, &e));
    cJSON_Delete(j); j = envelope();
    cJSON_ReplaceItemInObject(j, "device_session_id", cJSON_CreateString(cid));
    assert(!protocol_envelope(j, &s, 1000000, 1100000, &e));
    cJSON_Delete(j); j = envelope();
    cJSON *c = cJSON_GetObjectItemCaseSensitive(j, "command");
    cJSON_ReplaceItemInObject(c, "sequence", cJSON_CreateNumber(1));
    assert(!protocol_envelope(j, &s, 1000000, 1100000, &e));
    cJSON_Delete(j); j = envelope(); c = cJSON_GetObjectItemCaseSensitive(j, "command");
    cJSON_ReplaceItemInObject(c, "generation", cJSON_CreateNumber(2));
    assert(!protocol_envelope(j, &s, 1000000, 1100000, &e));
    cJSON_Delete(j); j = envelope(); c = cJSON_GetObjectItemCaseSensitive(j, "command");
    cJSON_ReplaceItemInObject(c, "kind", cJSON_CreateString("STOP"));
    cJSON_ReplaceItemInObject(c, "direction", cJSON_CreateString("STOP"));
    cJSON_ReplaceItemInObject(c, "mode", cJSON_CreateString("AUTO"));
    cJSON_ReplaceItemInObject(j, "requested_mode", cJSON_CreateString("AUTO"));
    assert(!protocol_envelope(j, &s, 1000000, 1100000, &e));
    cJSON_Delete(j); j = envelope();
    cJSON_ReplaceItemInObject(j, "control_authorized", cJSON_CreateFalse());
    assert(!protocol_envelope(j, &s, 1000000, 1100000, &e));
    cJSON_ReplaceItemInObject(j, "command", cJSON_CreateNull());
    cJSON_ReplaceItemInObject(j, "authorization_expires_at", cJSON_CreateNull());
    assert(protocol_envelope(j, &s, 1000000, 1100000, &e) && !e.authorized);
    assert(!strcmp(e.lease_id, lid)); // No motion command does not end the borrow/power.
    cJSON_ReplaceItemInObject(j, "control_session_id", cJSON_CreateNull());
    assert(protocol_envelope(j, &s, 1000000, 1100000, &e) && !e.lease_id[0]);
    cJSON_ReplaceItemInObject(j, "control_session_id", cJSON_CreateString("bad"));
    assert(!protocol_envelope(j, &s, 1000000, 1100000, &e));
    cJSON_Delete(j); j = envelope();
    cJSON_ReplaceItemInObject(j, "control_session_id", cJSON_CreateString(sid));
    assert(!protocol_envelope(j, &s, 1000000, 1100000, &e)); // Borrow/command identity must match.
    cJSON_DeleteItemFromObject(j, "control_session_id");
    assert(protocol_envelope(j, &s, 1000000, 1100000, &e) && !strcmp(e.lease_id, lid));
    cJSON_Delete(j);

    command_t command = {.sequence = 2, .generation = 3, .kind = KIND_MODE,
        .mode = MODE_MANUAL, .direction = MOVE_STOP, .safe_handoff = true};
    strcpy(command.id, cid); strcpy(command.robot_id, robot); strcpy(command.lease_id, lid);
    robot_snapshot_t snapshot = {.mode = MODE_MANUAL, .movement = MOVE_STOP, .sequence = 2,
        .generation = 3, .applied_sequence = 2, .sensor = {.valid = false}};
    cJSON *out = cJSON_CreateObject();
    for (int status = ACK_RECEIVED; status <= ACK_FAILED; ++status) {
        char *body = protocol_ack_body(&command, (ack_status_t)status);
        assert(body);
        cJSON *ack = cJSON_Parse(body); assert(ack);
        cJSON_AddItemToObject(out, ack_name((ack_status_t)status), ack);
        cJSON_free(body);
    }
    char *body = telemetry_body(&s, &snapshot, 1, 1000000);
    cJSON *telemetry = cJSON_Parse(body); assert(telemetry);
    assert(cJSON_IsNull(cJSON_GetObjectItemCaseSensitive(telemetry, "distance_cm")));
    assert(!strcmp(cJSON_GetObjectItemCaseSensitive(telemetry, "obstacle_status")->valuestring, "SENSOR_ERROR"));
    cJSON_AddItemToObject(out, "telemetry", telemetry); cJSON_free(body);
    if (argc == 2 && !strcmp(argv[1], "--contract-json")) {
        char *json = cJSON_PrintUnformatted(out); puts(json); cJSON_free(json);
    } else puts("Protocol assertions passed: UTC, identity, sequencing, TTL, STOP and JSON serializers");
    cJSON_Delete(out);
    return 0;
}
