#include "robot_internal.h"
#include <string.h>
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
    if (outputs_off) { relay_set(false); r->public.relay = false; }
}

void robot_invalidate_locked(robot_runtime_t *r, bool reset)
{
    robot_stop_locked(r, true);
    r->public.authorized = false;
    r->ready = false;
    r->public.deadline_us = 0;
    r->inhibited_sequence = r->processed_sequence;
    r->phase = AUTO_HALT;
    if (reset && !r->public.needs_reset) ++r->revision;
    r->public.needs_reset |= reset;
}

void robot_angle_locked(robot_runtime_t *r, int angle, int64_t now)
{
    if (r->angle == angle) return;
    robot_stop_locked(r, false);
    if (servo_set_angle(angle) != ESP_OK) {
        r->hardware_fault = true;
        robot_invalidate_locked(r, true);
        return;
    }
    r->angle = angle; r->servo_changed_us = now;
    r->public.sensor.settling = true;
    r->public.sensor.valid = false;
}

bool robot_center_fresh(const robot_runtime_t *r, int64_t now)
{
    return r->angle == SERVO_CENTER && r->public.sensor.angle == SERVO_CENTER
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
    runtime.angle = SERVO_CENTER;
    runtime.servo_changed_us = esp_timer_get_time();
    runtime.public.sensor.settling = true;
    runtime.public.obstacle = OBS_SENSOR_ERROR;
    runtime.public.needs_reset = true;
    runtime.phase = AUTO_HALT;
    return ESP_OK;
}

void robot_fault(bool new_session)
{
    if (!mutex) { motor_stop(); relay_set(false); return; }
    LOCK(); robot_invalidate_locked(&runtime, new_session); UNLOCK();
}
void robot_link_lost(void) { robot_fault(true); }
void robot_idle(void)
{
    LOCK();
    if (runtime.public.authorized || runtime.public.mode == MODE_AUTO)
        robot_invalidate_locked(&runtime, runtime.public.mode == MODE_AUTO);
    else robot_stop_locked(&runtime, false);
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
            r->blind_started_us = 0; r->blind_blocked = false;
            r->ready = false; // Wait for successful APPLIED receipt before allowing Auto.
        } else if (c->kind == KIND_MOVE && c->direction == MOVE_FORWARD) {
            r->blind_started_us = 0;
        }
    } else {
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
        sample.settling = sample.at_us < pose_at_start + SERVO_SETTLE_US;
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
    if (r->public.authorized && r->ready && !r->public.needs_reset && r->config->motors_enabled) {
        movement = r->public.mode == MODE_AUTO ? auto_tick_locked(r, now, &speed)
                                             : manual_tick_locked(r, now, &speed);
    }
    if (motor_set(movement, speed) != ESP_OK) {
        r->hardware_fault = true; robot_invalidate_locked(r, true);
    } else r->public.movement = movement;
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
    bool allowed = off || (runtime.config->relay_console && runtime.public.movement == MOVE_STOP
                          && esp_timer_get_time() < runtime.poll_deadline_us);
    if (allowed) {
        bool on = off ? false : strcmp(operation, "on") == 0 ? true : !runtime.public.relay;
        relay_set(on); runtime.public.relay = on;
    }
    UNLOCK(); return allowed;
}
