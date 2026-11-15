#pragma once
#include "types.h"
#include "cJSON.h"

typedef struct {
    char robot_id[UUID_LEN], session_id[UUID_LEN];
    uint64_t sequence, generation;
    uint32_t heartbeat_ms, offline_ms, poll_ms, telemetry_ms, manual_ttl_ms, mode_ttl_ms;
} session_t;
typedef struct {
    uint64_t sequence, generation;
    bool authorized, mode_pending;
    command_t command;
} envelope_t;

bool protocol_uuid(const char *text);
bool protocol_uint(const cJSON *object, const char *key, uint64_t *value);
bool protocol_time(const char *text, int64_t *microseconds);
bool protocol_auth(const cJSON *json, session_t *session);
bool protocol_envelope(const cJSON *json, const session_t *session, int64_t request_start,
                       int64_t received_us, envelope_t *envelope);
bool protocol_heartbeat(const cJSON *json, const session_t *session, uint64_t sequence,
                        int64_t request_start, int64_t received_us, int64_t *deadline,
                        uint64_t *server_seq, uint64_t *server_gen);
bool protocol_ack_receipt(const cJSON *json, const session_t *session, const command_t *command, ack_status_t status);
bool protocol_telemetry_receipt(const cJSON *json, const session_t *session, uint64_t sample);
char *protocol_ack_body(const command_t *command, ack_status_t status);
char *telemetry_body(const session_t *session, const robot_snapshot_t *snapshot, uint64_t sample, int64_t now);
