// ver2_6_esp32.ino loop/performRecoveryManeuver/backUpAndTurn,
// expressed as cancellable states for the web lease/permit controller.
#include "robot_internal.h"
#include "esp_log.h"
#include <math.h>

static void finish_recovery(robot_runtime_t *r, int64_t now)
{
    r->auto_last_distance = -1;
    r->auto_distance_changed_us = now;
    r->phase = AUTO_DRIVE;
}

static void look(robot_runtime_t *r, int angle, auto_phase_t phase, int64_t now)
{
    robot_angle_locked(r, angle, now);
    r->phase = phase;
    r->phase_deadline_us = 0;
    ESP_LOGI("auto", "ver2_6: looking %s", angle == SERVO_LEFT ? "LEFT" : "RIGHT");
}

static bool reading(robot_runtime_t *r, int angle, int64_t now, float *cm)
{
    if (r->angle != angle || r->servo_target != angle) return false;
    if (!r->phase_deadline_us)
        r->phase_deadline_us = r->servo_changed_us + SERVO_SETTLE_US + AUTO_SCAN_SAMPLE_WAIT_US;
    sensor_reading_t *s = &r->public.sensor;
    if (s->valid && !s->settling && s->angle == angle
        && s->at_us >= r->servo_changed_us + SERVO_SETTLE_US
        && now - s->at_us <= SENSOR_MAX_AGE_US) { *cm = s->distance_cm; return true; }
    if (now >= r->phase_deadline_us) { *cm = -1; return true; }
    return false;
}

static void center(robot_runtime_t *r, movement_t turn, int64_t now)
{
    r->turn = turn;
    robot_angle_locked(r, SERVO_CENTER, now);
    r->phase = AUTO_CENTER;
    r->phase_deadline_us = now + 200000; // reference's center wait; settling remains mandatory.
}

movement_t auto_tick_locked(robot_runtime_t *r, int64_t now, uint8_t *speed)
{
    switch (r->phase) {
    case AUTO_DRIVE: {
        if (!robot_center_fresh(r, now)) return MOVE_STOP;
        float distance = r->public.sensor.distance_cm;
        if (fabsf(distance - r->auto_last_distance) > 5.0f) {
            r->auto_last_distance = distance;
            r->auto_distance_changed_us = now;
        }
        if (now - r->auto_distance_changed_us >= 3000000) {
            ESP_LOGI("auto", "ver2_6: STUCK heuristic; backup and LEFT");
            center(r, MOVE_LEFT, now);
        } else if (distance >= STOP_CM) {
            *speed = distance >= WARN_CM ? r->config->full_speed : r->config->slow_speed;
            return MOVE_FORWARD;
        } else look(r, SERVO_LEFT, AUTO_LEFT, now);
        break;
    }
    case AUTO_LEFT:
        if (reading(r, SERVO_LEFT, now, &r->left_cm)) {
            if (r->left_cm >= STOP_CM) center(r, MOVE_LEFT, now);
            else look(r, SERVO_RIGHT, AUTO_RIGHT, now);
        }
        break;
    case AUTO_RIGHT:
        if (reading(r, SERVO_RIGHT, now, &r->right_cm))
            center(r, r->right_cm >= STOP_CM ? MOVE_RIGHT : MOVE_STOP, now);
        break;
    case AUTO_CENTER:
        if (now >= r->phase_deadline_us && robot_center_fresh(r, now)) {
            if (r->turn == MOVE_STOP) finish_recovery(r, now);
            else {
                r->phase = AUTO_BACKUP;
                r->phase_deadline_us = now + r->public.auto_backup_ms * 1000LL;
                *speed = r->config->turn_speed;
                ESP_LOGI("auto", "ver2_6: BACKUP %lums then %s", (unsigned long)r->public.auto_backup_ms,
                    r->turn == MOVE_LEFT ? "LEFT" : "RIGHT");
                return MOVE_BACKWARD;
            }
        }
        break;
    case AUTO_BACKUP:
        if (!robot_center_fresh(r, now)) return MOVE_STOP;
        if (now < r->phase_deadline_us) { *speed = r->config->turn_speed; return MOVE_BACKWARD; }
        r->phase = AUTO_BRAKE;
        r->phase_deadline_us = now + 100000;
        break;
    case AUTO_BRAKE:
        if (now >= r->phase_deadline_us && robot_center_fresh(r, now)) {
            r->phase = AUTO_TURN;
            uint32_t ms = r->turn == MOVE_LEFT ? r->public.auto_turn_left_ms : r->public.auto_turn_right_ms;
            r->phase_deadline_us = now + ms * 1000LL;
            *speed = r->config->turn_speed;
            return r->turn;
        }
        break;
    case AUTO_TURN:
        if (!robot_center_fresh(r, now)) return MOVE_STOP;
        if (now < r->phase_deadline_us) { *speed = r->config->turn_speed; return r->turn; }
        r->phase = AUTO_FRONT;
        r->phase_deadline_us = now + 100000;
        break;
    case AUTO_FRONT:
        if (now >= r->phase_deadline_us && robot_center_fresh(r, now)
            && r->public.sensor.at_us > r->phase_deadline_us) finish_recovery(r, now);
        break;
    case AUTO_BACKUP_READY: // No longer used by the reference algorithm.
    case AUTO_HALT:
        break;
    }
    return MOVE_STOP;
}
