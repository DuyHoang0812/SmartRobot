#include "robot_internal.h"

static bool sample_at(const robot_runtime_t *r, int angle, int64_t now)
{
    return r->angle == angle && r->public.sensor.angle == angle && r->public.sensor.valid
        && !r->public.sensor.settling && now - r->public.sensor.at_us <= SENSOR_MAX_AGE_US;
}

movement_t auto_tick_locked(robot_runtime_t *r, int64_t now, uint8_t *speed)
{
    switch (r->phase) {
    case AUTO_DRIVE:
        if (!robot_center_fresh(r, now)) return MOVE_STOP;
        if (r->public.sensor.distance_cm >= STOP_CM) {
            *speed = r->public.sensor.distance_cm >= WARN_CM ? r->config->full_speed : r->config->slow_speed;
            return MOVE_FORWARD;
        }
        r->left_cm = r->right_cm = -1;
        robot_angle_locked(r, SERVO_LEFT, now);
        r->phase = AUTO_LEFT;
        break;
    case AUTO_LEFT:
        if (sample_at(r, SERVO_LEFT, now)) {
            r->left_cm = r->public.sensor.distance_cm;
            robot_angle_locked(r, SERVO_RIGHT, now);
            r->phase = AUTO_RIGHT;
        }
        break;
    case AUTO_RIGHT:
        if (sample_at(r, SERVO_RIGHT, now)) {
            r->right_cm = r->public.sensor.distance_cm;
            r->turn = r->left_cm >= r->right_cm ? MOVE_LEFT : MOVE_RIGHT;
            robot_angle_locked(r, SERVO_CENTER, now);
            r->phase = r->left_cm >= WARN_CM || r->right_cm >= WARN_CM ? AUTO_CENTER : AUTO_HALT;
        }
        break;
    case AUTO_CENTER:
        if (robot_center_fresh(r, now)) {
            r->phase = AUTO_TURN;
            r->phase_deadline_us = now + 400000; // Original turn time, never an unobserved backup.
        }
        break;
    case AUTO_TURN:
        if (!robot_center_fresh(r, now)) return MOVE_STOP;
        if (now < r->phase_deadline_us) { *speed = r->config->turn_speed; return r->turn; }
        r->phase = AUTO_FRONT;
        r->phase_deadline_us = now;
        break;
    case AUTO_FRONT:
        // Require a NEW front reading after stopping the turn, not the pre-turn sample.
        if (robot_center_fresh(r, now) && r->public.sensor.at_us > r->phase_deadline_us) {
            r->phase = r->public.sensor.distance_cm >= STOP_CM ? AUTO_DRIVE : AUTO_HALT;
        }
        break;
    case AUTO_HALT:
        break; // Explicit mode/lease handoff is needed to restart a failed avoidance.
    }
    return MOVE_STOP;
}
