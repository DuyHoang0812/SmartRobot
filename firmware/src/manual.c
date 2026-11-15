#include "robot_internal.h"

movement_t manual_tick_locked(robot_runtime_t *r, int64_t now, uint8_t *speed)
{
    if (r->intent.kind != KIND_MOVE || r->processed_sequence <= r->inhibited_sequence
        || !robot_center_fresh(r, now)) return MOVE_STOP;
    movement_t desired = r->intent.direction;
    if (desired == MOVE_FORWARD) {
        if (r->public.sensor.distance_cm < STOP_CM) {
            r->inhibited_sequence = r->processed_sequence;
            return MOVE_STOP; // Clearing the obstacle does not resume this same command.
        }
        *speed = r->config->full_speed;
    } else {
        // Rear/sides are unobserved. Explicit opt-in and a non-refreshable burst limit.
        if (!r->config->allow_blind_manual || r->blind_blocked) return MOVE_STOP;
        if (!r->blind_started_us) r->blind_started_us = now;
        if (now - r->blind_started_us >= r->config->blind_ms * 1000LL) {
            r->blind_blocked = true;
            return MOVE_STOP;
        }
        *speed = r->config->turn_speed;
    }
    return desired;
}
