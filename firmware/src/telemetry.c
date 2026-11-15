#include "protocol.h"
#include "board.h"
#include <math.h>

char *telemetry_body(const session_t *s, const robot_snapshot_t *r, uint64_t sample, int64_t now)
{
    cJSON *j = cJSON_CreateObject();
    if (!j) return NULL;
    cJSON_AddStringToObject(j, "robot_id", s->robot_id);
    cJSON_AddNumberToObject(j, "sample_sequence", (double)sample);
    cJSON_AddNumberToObject(j, "sequence", (double)r->sequence);
    cJSON_AddNumberToObject(j, "generation", (double)r->generation);
    if (r->applied_sequence) cJSON_AddNumberToObject(j, "command_sequence_applied", (double)r->applied_sequence);
    else cJSON_AddNullToObject(j, "command_sequence_applied");
    bool valid = r->sensor.valid && !r->sensor.settling && now - r->sensor.at_us <= SENSOR_MAX_AGE_US
        && isfinite(r->sensor.distance_cm);
    if (valid) cJSON_AddNumberToObject(j, "distance_cm", r->sensor.distance_cm);
    else cJSON_AddNullToObject(j, "distance_cm");
    obstacle_t obstacle = !valid ? OBS_SENSOR_ERROR : r->sensor.distance_cm < STOP_CM ? OBS_BLOCKED : OBS_CLEAR;
    cJSON_AddStringToObject(j, "obstacle_status", obstacle_name(obstacle));
    cJSON_AddStringToObject(j, "actual_mode", mode_name(r->mode));
    cJSON_AddStringToObject(j, "actual_movement", movement_name(r->movement));
    cJSON_AddBoolToObject(j, "buzzer_active", r->buzzer);
    char *body = cJSON_PrintUnformatted(j); cJSON_Delete(j); return body;
}
