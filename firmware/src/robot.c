#include "robot_internal.h"
#include <string.h>
#include <math.h>
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

static SemaphoreHandle_t mutex;
static robot_runtime_t runtime;
#define LOCK() xSemaphoreTake(mutex, portMAX_DELAY)
#define UNLOCK() xSemaphoreGive(mutex)

void robot_stop_locked(robot_runtime_t *r, bool outputs_off)
{
    motor_stop();
    r->public.movement = MOVE_STOP;
    r->public.motor_duty = 0;
    r->public.left_motor_duty = r->public.right_motor_duty = 0;
    if (outputs_off) {
        relay_set(false); r->public.relay = false; r->motor_power_at_us = 0;
    }
}

void robot_invalidate_locked(robot_runtime_t *r, bool reset)
{
    robot_stop_locked(r, reset);
    r->public.authorized = false;
    r->ready = false;
    r->awaiting_command = true;
    r->public.deadline_us = 0;
    r->inhibited_sequence = r->processed_sequence;
    r->phase = AUTO_HALT;
    r->recovery_clear_since_us = 0;
    if (reset && !r->public.needs_reset) ++r->revision;
    r->public.needs_reset |= reset;
}

void robot_reset_locked(robot_runtime_t *r, const char *reason)
{
    if (!r->public.needs_reset) r->reset_reason = reason;
    robot_invalidate_locked(r, true);
}

void robot_angle_locked(robot_runtime_t *r, int angle, int64_t now)
{
    if (r->servo_target == angle) return;
    robot_stop_locked(r, false);
    // Match ver2_6 Servo.write(): command the target directly, then wait for settling.
    if (servo_set_angle(angle) != ESP_OK) {
        r->hardware_fault = true;
        robot_reset_locked(r, "servo_driver");
        return;
    }
    r->angle = r->servo_target = angle; r->servo_changed_us = now;
    r->public.sensor.settling = true;
    r->public.sensor.valid = false;
}

bool robot_center_fresh(const robot_runtime_t *r, int64_t now)
{
    return r->angle == SERVO_CENTER && r->servo_target == SERVO_CENTER && r->public.sensor.angle == SERVO_CENTER
        && !r->public.sensor.settling && r->public.sensor.valid
        && now - r->public.sensor.at_us <= SENSOR_MAX_AGE_US
        && r->public.sensor.at_us >= r->servo_changed_us + SERVO_SETTLE_US;
}

esp_err_t robot_init(const robot_config_t *config)
{
    mutex = xSemaphoreCreateMutex();
    if (!mutex) return ESP_ERR_NO_MEM;
    memset(&runtime, 0, sizeof(runtime));
    runtime.config = config;
    runtime.public.left_motor_percent = config->left_motor_percent ? config->left_motor_percent : DEFAULT_LEFT_MOTOR_PERCENT;
    runtime.public.right_motor_percent = config->right_motor_percent ? config->right_motor_percent : DEFAULT_RIGHT_MOTOR_PERCENT;
    runtime.public.auto_clearance_cm = config->auto_clearance_cm ? config->auto_clearance_cm : DEFAULT_AUTO_CLEARANCE_CM;
    runtime.public.auto_backup_ms = config->auto_backup_ms ? config->auto_backup_ms : DEFAULT_AUTO_BACKUP_MS;
    runtime.public.auto_turn_left_ms = config->auto_turn_left_ms ? config->auto_turn_left_ms : DEFAULT_AUTO_TURN_MS;
    runtime.public.auto_turn_right_ms = config->auto_turn_right_ms ? config->auto_turn_right_ms : DEFAULT_AUTO_TURN_MS;
    motor_set_trim(runtime.public.left_motor_percent, runtime.public.right_motor_percent);
    runtime.angle = runtime.servo_target = SERVO_CENTER;
    runtime.servo_changed_us = esp_timer_get_time();
    runtime.public.sensor.settling = true;
    runtime.public.obstacle = OBS_SENSOR_ERROR;
    runtime.public.needs_reset = true;
    runtime.reset_reason = "startup";
    runtime.phase = AUTO_HALT;
    return ESP_OK;
}

void robot_fault(bool new_session)
{
    if (!mutex) { motor_stop(); relay_set(false); return; }
    LOCK();
    if (new_session) robot_reset_locked(&runtime, "communication_failure");
    else robot_invalidate_locked(&runtime, false);
    UNLOCK();
}
void robot_link_lost(void)
{
    if (!mutex) return;
    LOCK(); robot_reset_locked(&runtime, "wifi_disconnected"); UNLOCK();
}
void robot_command_conflict(void)
{
    LOCK();
    robot_stop_locked(&runtime, false);
    runtime.awaiting_command = true;
    runtime.inhibited_sequence = runtime.processed_sequence;
    runtime.recovery_clear_since_us = 0;
    // Keep the previous mode confirmation/fence and ORIGINAL deadline. A newer command
    // can reauthorize only after its APPLIED receipt; expiry/sensor/network watchdogs still run.
    UNLOCK();
}
const char *robot_reset_reason(void)
{
    LOCK(); const char *reason = runtime.reset_reason; UNLOCK();
    return reason ? reason : "unspecified";
}
void robot_idle(void)
{
    LOCK();
    if (runtime.public.authorized || runtime.public.mode == MODE_AUTO) {
        if (runtime.public.mode == MODE_AUTO) robot_reset_locked(&runtime, "auto_authorization_removed");
        else robot_invalidate_locked(&runtime, false);
    } else robot_stop_locked(&runtime, false);
    runtime.processed_sequence = runtime.public.sequence;
    runtime.inhibited_sequence = runtime.public.sequence;
    UNLOCK();
}
void robot_duplicate_deadline(const command_t *c)
{
    LOCK();
    if (runtime.processed_sequence == c->sequence && runtime.public.generation == c->generation
        && c->deadline_us < runtime.public.deadline_us) runtime.public.deadline_us = c->deadline_us;
    UNLOCK();
}
bool robot_needs_reset(void) { LOCK(); bool v = runtime.public.needs_reset; UNLOCK(); return v; }
bool robot_hardware_fault(void) { LOCK(); bool v = runtime.hardware_fault; UNLOCK(); return v; }
uint32_t robot_revision(void) { LOCK(); uint32_t v = runtime.revision; UNLOCK(); return v; }

void robot_new_session(uint64_t sequence, uint64_t generation)
{
    LOCK();
    robot_stop_locked(&runtime, true);
    runtime.borrow_id[0] = 0; runtime.public.borrowed = false;
    robot_invalidate_locked(&runtime, false);
    runtime.public.sequence = sequence; runtime.public.generation = generation;
    runtime.processed_sequence = sequence;
    runtime.inhibited_sequence = sequence;
    runtime.public.applied_sequence = 0;
    runtime.public.mode = MODE_MANUAL;
    runtime.public.needs_reset = false;
    runtime.blind_started_us = 0; runtime.blind_blocked = false;
    runtime.heartbeat_deadline_us = 0; runtime.poll_deadline_us = 0;
    robot_angle_locked(&runtime, SERVO_CENTER, esp_timer_get_time());
    UNLOCK();
}

bool robot_observe(uint64_t sequence, uint64_t generation)
{
    LOCK();
    bool valid = generation >= runtime.public.generation && sequence >= runtime.public.sequence;
    if (valid) {
        if (generation != runtime.public.generation) {
            robot_invalidate_locked(&runtime, false);
            runtime.public.applied_sequence = 0;
            robot_angle_locked(&runtime, SERVO_CENTER, esp_timer_get_time());
        }
        runtime.public.sequence = sequence; runtime.public.generation = generation;
    }
    UNLOCK();
    return valid;
}

void robot_poll_alive(int64_t now_us)
{
    LOCK(); runtime.poll_deadline_us = now_us + 1000000; UNLOCK();
}
void robot_heartbeat_alive(int64_t deadline_us)
{
    LOCK(); runtime.heartbeat_deadline_us = deadline_us; UNLOCK();
}

void robot_borrow_update(const char *lease_id)
{
    LOCK();
    const char *next = lease_id ? lease_id : "";
    // A reconnect/MODE must not buy another blind reverse against the same obstacle.
    // Keep this identity across device-session resets; a genuinely new borrow resets it.
    if (next[0] && strcmp(runtime.recovery_borrow_id, next)) {
        memcpy(runtime.recovery_borrow_id, next, UUID_LEN);
        runtime.recovery_backups = 0; runtime.failed_turn = MOVE_STOP;
        runtime.recovery_clear_since_us = 0;
    }
    if (strcmp(runtime.borrow_id, next)) {
        robot_invalidate_locked(&runtime, false);
        robot_stop_locked(&runtime, true);
        if (next[0]) memcpy(runtime.borrow_id, next, UUID_LEN);
        else runtime.borrow_id[0] = 0;
        runtime.public.borrowed = next[0] != 0;
    }
    UNLOCK();
}

ack_status_t robot_accept(const command_t *c)
{
    LOCK();
    robot_runtime_t *r = &runtime;
    int64_t now = esp_timer_get_time();
    safety_tick_locked(r, now); // A late KEEPALIVE cannot sneak past an expired old permit.
    ack_status_t result = ACK_APPLIED;
    if (r->hardware_fault || r->public.needs_reset || c->generation != r->public.generation
        || c->sequence < r->public.sequence || c->sequence <= r->processed_sequence
        || c->deadline_us <= now || now >= r->heartbeat_deadline_us) {
        result = ACK_FAILED;
    } else if (!r->public.borrowed || strcmp(c->lease_id, r->borrow_id)) {
        result = ACK_REJECTED;
    } else if (c->kind == KIND_STOP && c->mode != MODE_MANUAL) {
        result = ACK_REJECTED;
    } else if ((c->kind == KIND_MOVE || c->mode == MODE_AUTO) && !r->config->motors_enabled) {
        result = ACK_REJECTED;
    } else if (c->kind == KIND_MOVE && (r->public.mode != MODE_MANUAL || c->mode != MODE_MANUAL
        || (!r->config->allow_blind_manual && c->direction != MOVE_FORWARD))) {
        result = ACK_REJECTED;
    } else if (c->kind == KIND_KEEPALIVE &&
               (r->public.mode != MODE_AUTO || !r->ready || !r->public.authorized
                || strcmp(c->lease_id, r->intent.lease_id))) {
        result = ACK_REJECTED;
    } else if (r->public.authorized && c->generation == r->intent.generation
               && strcmp(c->lease_id, r->intent.lease_id)) {
        result = ACK_REJECTED;
    }
    if (result == ACK_APPLIED) {
        r->intent = *c;
        r->processed_sequence = c->sequence;
        r->public.sequence = c->sequence;
        r->public.deadline_us = c->deadline_us;
        r->public.authorized = true;
        if (c->kind == KIND_MODE || c->kind == KIND_STOP) {
            robot_stop_locked(r, false);
            robot_angle_locked(r, SERVO_CENTER, now);
            r->public.mode = c->mode;
            r->phase = AUTO_DRIVE;
            r->auto_last_distance = -1;
            r->auto_distance_changed_us = now;
            r->blind_started_us = 0; r->blind_blocked = false;
            r->recovery_clear_since_us = 0;
            r->ready = false; // Wait for successful APPLIED receipt before allowing Auto.
        } else if (c->kind == KIND_MOVE && c->direction == MOVE_FORWARD) {
            r->blind_started_us = 0;
        }
    } else {
        ESP_LOGW("control", "Command denied: seq=%llu status=%d motors=%d blind=%d reset=%d",
            (unsigned long long)c->sequence, result, r->config->motors_enabled,
            r->config->allow_blind_manual, r->public.needs_reset);
        robot_invalidate_locked(r, false);
    }
    UNLOCK();
    return result;
}

bool robot_ack_commit(const command_t *c, uint32_t revision)
{
    LOCK();
    bool valid = revision == runtime.revision && !runtime.public.needs_reset
        && runtime.processed_sequence == c->sequence && runtime.public.generation == c->generation
        && runtime.public.authorized && esp_timer_get_time() < runtime.public.deadline_us;
    if (valid) {
        runtime.public.applied_sequence = c->sequence;
        runtime.ready = true;
        runtime.awaiting_command = false;
    }
    UNLOCK();
    return valid;
}

void robot_snapshot(robot_snapshot_t *snapshot)
{
    LOCK(); *snapshot = runtime.public; UNLOCK();
}
void robot_servo_pose(int *angle, int64_t *changed_us)
{
    LOCK(); *angle = runtime.angle; *changed_us = runtime.servo_changed_us; UNLOCK();
}
void robot_sensor_publish(sensor_reading_t sample, int64_t pose_at_start)
{
    LOCK();
    if (runtime.servo_changed_us == pose_at_start && sample.angle == runtime.angle) {
        sample.settling = runtime.angle != runtime.servo_target || sample.at_us < pose_at_start + SERVO_SETTLE_US;
        runtime.public.sensor = sample;
    }
    UNLOCK();
}

void robot_controller_tick(void)
{
    LOCK();
    robot_runtime_t *r = &runtime;
    int64_t now = esp_timer_get_time();
    safety_tick_locked(r, now);
    movement_t movement = MOVE_STOP;
    uint8_t speed = 0;
    if (r->public.authorized && r->ready && !r->awaiting_command
        && !r->public.needs_reset && r->config->motors_enabled) {
        movement = r->public.mode == MODE_AUTO ? auto_tick_locked(r, now, &speed)
                                             : manual_tick_locked(r, now, &speed);
    }
    movement_t previous = r->public.movement;
    uint8_t previous_duty = r->public.motor_duty;
    // Motor supply belongs to the borrow, independently of Manual STOP or Auto movement.
    bool power = r->public.borrowed && r->config->motors_enabled
        && !r->public.needs_reset && !r->hardware_fault;
    if (power) {
        if (!r->public.relay) {
            relay_set(true); r->public.relay = true; r->motor_power_at_us = now;
            ESP_LOGI("motor", "Borrow active: motor power relay ON (held until return)");
        }
        if (now - r->motor_power_at_us < MOTOR_POWER_SETTLE_US) { movement = MOVE_STOP; speed = 0; }
    } else {
        if (r->public.relay) ESP_LOGI("motor", "Borrow ended or fault: motor power relay OFF");
        robot_stop_locked(r, true); movement = MOVE_STOP; speed = 0;
    }
    if (motor_set(movement, speed) != ESP_OK) {
        r->hardware_fault = true; robot_reset_locked(r, "motor_driver");
    } else {
        r->public.movement = movement;
        r->public.motor_duty = movement == MOVE_STOP ? 0 : speed;
        motor_get_duties(&r->public.left_motor_duty, &r->public.right_motor_duty);
    }
    if (previous != r->public.movement || previous_duty != r->public.motor_duty)
        ESP_LOGI("motor", "Output direction=%d base=%u/255 left=%u right=%u (wheel speed unmeasured)",
            r->public.movement, r->public.motor_duty, r->public.left_motor_duty, r->public.right_motor_duty);
    sensor_reading_t *s = &r->public.sensor;
    bool fresh = s->valid && !s->settling && now - s->at_us <= SENSOR_MAX_AGE_US;
    r->public.obstacle = !fresh ? OBS_SENSOR_ERROR : s->distance_cm < STOP_CM ? OBS_BLOCKED : OBS_CLEAR;
    bool alarm = fresh && s->distance_cm < STOP_CM;
    if (!fresh && !s->settling && r->public.authorized) alarm = true;
    if (fresh && r->public.mode == MODE_AUTO && s->distance_cm >= STOP_CM && s->distance_cm < WARN_CM)
        alarm = (now / 100000) % 2 == 0;
    r->public.buzzer = alarm;
    buzzer_set(alarm);
    UNLOCK();
}
void robot_watchdog_tick(void)
{
    LOCK(); safety_tick_locked(&runtime, esp_timer_get_time()); UNLOCK();
}

bool robot_relay_control(const char *operation)
{
    LOCK();
    bool off = strcmp(operation, "off") == 0;
    if (off) robot_reset_locked(&runtime, "local_relay_off");
    UNLOCK(); return off; // Motor supply is managed only by validated drive intent.
}

static bool configuration_allowed(void)
{
    return runtime.public.mode == MODE_MANUAL && runtime.public.movement == MOVE_STOP
        && !(runtime.public.authorized && runtime.intent.kind == KIND_MOVE) && !runtime.hardware_fault;
}

bool robot_motor_trim(float left_percent, float right_percent)
{
    if (!isfinite(left_percent) || !isfinite(right_percent)
        || left_percent < 50 || left_percent > 150 || right_percent < 50 || right_percent > 150) return false;
    left_percent = (uint32_t)(left_percent * 10 + 0.5f) / 10.0f;
    right_percent = (uint32_t)(right_percent * 10 + 0.5f) / 10.0f;
    LOCK();
    bool allowed = configuration_allowed();
    if (allowed) {
        motor_set_trim(left_percent, right_percent);
        runtime.public.left_motor_percent = left_percent;
        runtime.public.right_motor_percent = right_percent;
    }
    UNLOCK(); return allowed;
}

bool robot_auto_configure(uint32_t clearance_cm, uint32_t backup_ms, uint32_t left_ms, uint32_t right_ms)
{
    if (clearance_cm < 15 || clearance_cm > 100 || backup_ms < 50 || backup_ms > 400
        || left_ms < 100 || left_ms > 1200 || right_ms < 100 || right_ms > 1200) return false;
    LOCK();
    bool allowed = configuration_allowed();
    if (allowed) {
        runtime.public.auto_clearance_cm = clearance_cm;
        runtime.public.auto_backup_ms = backup_ms;
        runtime.public.auto_turn_left_ms = left_ms;
        runtime.public.auto_turn_right_ms = right_ms;
    }
    UNLOCK(); return allowed;
}
