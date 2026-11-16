// Unit test API doubles inspect electrical output requests, never real wheel motion.
#include "robot.h"
#include "hardware.h"
#include "board.h"
#include "driver/ledc.h"
#include "driver/gpio.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static int64_t now = 1000000;
static unsigned duty[4];
static bool enabled[4];
static int pins[4];
static bool fail_driver;
static bool motor_power;
static int relay_level = -1;
static int relay_off_edges;
static int servo_moves;
static unsigned auto_reverse_bursts;
static int64_t auto_reverse_at;
int64_t esp_timer_get_time(void) { return now; }
int gpio_set_level(int pin, int level)
{
    if (pin == PIN_RELAY) {
        if (relay_level == 0 && level == 1) ++relay_off_edges;
        relay_level = level; motor_power = level == 0;
    }
    return ESP_OK;
}
int gpio_config(const gpio_config_t *config) { (void)config; return ESP_OK; }
int gpio_set_direction(int pin, int mode) { (void)pin; (void)mode; return ESP_OK; }
int ledc_timer_config(const ledc_timer_config_t *timer)
{
    assert(timer->freq_hz == 1000 && timer->duty_resolution == 8);
    return ESP_OK;
}
int ledc_channel_config(const ledc_channel_config_t *channel)
{
    assert(channel->channel >= 0 && channel->channel < 4);
    pins[channel->channel] = channel->gpio_num;
    return ESP_OK;
}
int ledc_stop(int mode, int channel, int idle)
{
    (void)mode; assert(idle == 0); enabled[channel] = false; return ESP_OK;
}
int ledc_set_duty(int mode, int channel, uint32_t value)
{
    (void)mode;
    if (fail_driver) return ESP_ERR_INVALID_STATE;
    duty[channel] = value; return ESP_OK;
}
int ledc_update_duty(int mode, int channel)
{
    (void)mode; enabled[channel] = true; return ESP_OK;
}
esp_err_t servo_set_angle(int angle)
{
    assert(angle >= 0 && angle <= 180);
    assert(angle == SERVO_LEFT || angle == SERVO_CENTER || angle == SERVO_RIGHT);
    ++servo_moves; return ESP_OK;
}

static command_t command = {0};
static void fresh_sensor(bool valid, float distance)
{
    int angle; int64_t pose;
    robot_servo_pose(&angle, &pose);
    sensor_reading_t reading = {.valid = valid, .distance_cm = distance, .angle = angle, .at_us = now};
    robot_sensor_publish(reading, pose);
    robot_poll_alive(now);
    robot_heartbeat_alive(now + 10000000);
}
static void stopped(void)
{
    robot_snapshot_t s; robot_snapshot(&s);
    assert(s.movement == MOVE_STOP && s.motor_duty == 0);
    for (int i = 0; i < 4; i++) assert(!enabled[i] || duty[i] == 0);
}
static void powered(bool on)
{
    robot_snapshot_t s; robot_snapshot(&s);
    assert(motor_power == on && s.relay == on && relay_level == (on ? 0 : 1));
}
static void output(movement_t direction, unsigned speed)
{
    const bool high[5][4] = {{0,0,0,0}, {1,0,1,0}, {0,1,0,1}, {0,1,1,0}, {1,0,0,1}};
    robot_snapshot_t s; robot_snapshot(&s);
    if (s.movement == MOVE_STOP && s.relay) {
        assert(motor_power);
        for (int i = 0; i < 4; i++) assert(!enabled[i] || duty[i] == 0);
        now += MOTOR_POWER_SETTLE_US;
        fresh_sensor(s.sensor.valid, s.sensor.distance_cm);
        robot_controller_tick(); robot_snapshot(&s);
    }
    assert(motor_power && s.relay);
    assert(s.movement == direction && s.motor_duty == speed);
    for (int i = 0; i < 4; i++) {
        float percent = i < 2 ? s.right_motor_percent : s.left_motor_percent;
        unsigned calibrated = (unsigned)(speed * percent / 100.0f + 0.5f);
        if (calibrated > 255) calibrated = 255;
        assert(enabled[i] && duty[i] == (high[direction][i] ? calibrated : 0));
    }
    unsigned expected_left = (unsigned)(speed * s.left_motor_percent / 100.0f + 0.5f);
    unsigned expected_right = (unsigned)(speed * s.right_motor_percent / 100.0f + 0.5f);
    assert(s.left_motor_duty == (expected_left > 255 ? 255 : expected_left));
    assert(s.right_motor_duty == (expected_right > 255 ? 255 : expected_right));
}
static void accept(command_kind_t kind, robot_mode_t mode, movement_t direction, bool commit)
{
    if (kind == KIND_MODE || kind == KIND_STOP) ++command.generation;
    ++command.sequence;
    command.kind = kind; command.mode = mode; command.direction = direction;
    command.deadline_us = now + (kind == KIND_MOVE ? 700000 : 3000000);
    assert(robot_observe(command.sequence, command.generation));
    assert(robot_accept(&command) == ACK_APPLIED);
    if (commit) assert(robot_ack_commit(&command, robot_revision()));
}
static void auto_scene(int milliseconds, float front, float left, float right)
{
    for (int elapsed = 0; elapsed < milliseconds; elapsed += 10) {
        now += 10000;
        int angle; int64_t pose;
        robot_servo_pose(&angle, &pose);
        float distance = angle == SERVO_LEFT ? left : angle == SERVO_RIGHT ? right : front;
        fresh_sensor(distance >= 0, distance);
        if (command.deadline_us - now <= 1500000)
            accept(KIND_KEEPALIVE, MODE_AUTO, MOVE_STOP, true);
        robot_snapshot_t before; robot_snapshot(&before);
        robot_controller_tick(); robot_watchdog_tick();
        robot_snapshot_t after; robot_snapshot(&after);
        if (before.movement != MOVE_BACKWARD && after.movement == MOVE_BACKWARD) {
            ++auto_reverse_bursts; auto_reverse_at = now;
        }
        if (before.movement == MOVE_BACKWARD && after.movement != MOVE_BACKWARD)
            assert(now - auto_reverse_at <= AUTO_BLOCKED_BACKUP_MAX_MS * 1000);
        assert(!robot_needs_reset()); powered(true);
    }
}
static void auto_until(movement_t movement, int limit_ms, float front, float left, float right)
{
    for (int elapsed = 0; elapsed < limit_ms; elapsed += 10) {
        auto_scene(10, front, left, right);
        robot_snapshot_t current; robot_snapshot(&current);
        if (current.movement == movement) { output(movement, 75); return; }
    }
    fprintf(stderr, "Auto did not reach movement %d within %dms\n", movement, limit_ms);
    assert(false);
}
static void auto_reference_regressions(void)
{
    accept(KIND_STOP, MODE_MANUAL, MOVE_STOP, true);
    robot_controller_tick(); stopped();
    assert(robot_motor_trim(100, 83.5f));
    assert(robot_auto_configure(15, 400, 400, 400));
    accept(KIND_MODE, MODE_AUTO, MOVE_STOP, true);
    auto_until(MOVE_BACKWARD, 10000, 8, 45, 100); // LEFT wins even when RIGHT is farther.
    int scans = servo_moves;
    auto_scene(390, 8, 45, 100); output(MOVE_BACKWARD, 75);
    auto_scene(10, 8, 45, 100); stopped();
    auto_scene(90, 8, 45, 100); stopped();
    auto_scene(10, 8, 45, 100); output(MOVE_LEFT, 75);
    assert(scans == servo_moves); // No right scan for a clear left side.
    auto_scene(390, 8, 45, 100); output(MOVE_LEFT, 75);
    auto_scene(10, 100, 45, 100); stopped();
    auto_scene(90, 100, 45, 100); stopped();
    auto_until(MOVE_FORWARD, 500, 100, 45, 100);
    assert(duty[0] == 63 && duty[2] == 75);

    accept(KIND_MODE, MODE_AUTO, MOVE_STOP, true);
    auto_until(MOVE_BACKWARD, 10000, 8, 8, 60);
    auto_until(MOVE_RIGHT, 1000, 8, 8, 60);
    // Web switching to Manual cancels a pivot immediately and keeps the borrow powered.
    accept(KIND_STOP, MODE_MANUAL, MOVE_STOP, true);
    robot_controller_tick(); stopped(); powered(true);
    accept(KIND_MODE, MODE_AUTO, MOVE_STOP, true);
    unsigned backups = auto_reverse_bursts;
    auto_scene(14000, 8, 8, 8); stopped();
    assert(auto_reverse_bursts == backups); // Reference returns to center if both sides blocked.
    accept(KIND_MODE, MODE_AUTO, MOVE_STOP, true);
    auto_scene(14000, 8, -1, -1); stopped();
    assert(auto_reverse_bursts == backups); // Unknown echo is not an invented clear path.

    accept(KIND_MODE, MODE_AUTO, MOVE_STOP, true);
    auto_until(MOVE_FORWARD, 10000, 100, 60, 60);
    auto_scene(2800, 100, 60, 60); output(MOVE_FORWARD, 75);
    auto_until(MOVE_BACKWARD, 1000, 100, 60, 60); // Reference 3-second/5cm STUCK heuristic.
    now = command.deadline_us + 1; fresh_sensor(true, 100);
    robot_watchdog_tick(); stopped(); powered(false); assert(robot_needs_reset());
    robot_new_session(command.sequence, command.generation);
    fresh_sensor(true, 100); robot_borrow_update(command.lease_id);
    accept(KIND_MODE, MODE_AUTO, MOVE_STOP, true);
    auto_until(MOVE_FORWARD, 10000, 100, 60, 60);
}
#ifdef DEVICE_RETRY_TEST
void test_delay(int ms)
{
    for (int i = 0; i < ms; i += 10) {
        now += (ms - i < 10 ? ms - i : 10) * 1000LL;
        int angle; int64_t pose;
        robot_servo_pose(&angle, &pose);
        sensor_reading_t sample = {.valid = true, .distance_cm = 100 + ((now / 1000000) % 2) * 10, .angle = angle, .at_us = now};
        robot_sensor_publish(sample, pose);
        robot_controller_tick(); robot_watchdog_tick();
    }
}
void test_network_setup(const robot_config_t *config)
{
    fail_driver = false; now = 1000000;
    assert(outputs_init() == ESP_OK); assert(motor_init() == ESP_OK);
    assert(robot_init(config) == ESP_OK); test_delay(610);
}
int runtime_suite_main(void)
#else
int main(void)
#endif
{
    robot_config_t config = {.motors_enabled = true, .allow_blind_manual = true,
        .blind_ms = 300, .full_speed = 75, .slow_speed = 30, .turn_speed = 75,
        .left_motor_percent = 100, .right_motor_percent = 100, .auto_clearance_cm = 30,
        .auto_backup_ms = 300, .auto_turn_left_ms = 400, .auto_turn_right_ms = 400};
    assert(outputs_init() == ESP_OK);
    assert(relay_level == 1 && !motor_power);
    assert(motor_init() == ESP_OK);
    assert(pins[0] == 19 && pins[1] == 21 && pins[2] == 5 && pins[3] == 18);
    assert(robot_init(&config) == ESP_OK);
    robot_new_session(0, 0);
    strcpy(command.lease_id, "55555555-5555-4555-8555-555555555555");
    now += SERVO_SETTLE_US + 1;
    fresh_sensor(true, 100);
    robot_borrow_update(command.lease_id);
    robot_controller_tick(); stopped(); powered(true);
    int power_cuts = relay_off_edges;
    accept(KIND_MODE, MODE_MANUAL, MOVE_STOP, true);
    robot_controller_tick(); stopped(); powered(true);
    for (movement_t direction = MOVE_FORWARD; direction <= MOVE_RIGHT; direction++) {
        fresh_sensor(true, 100);
        accept(KIND_MOVE, MODE_MANUAL, direction, true);
        robot_controller_tick(); output(direction, 75);
        accept(KIND_STOP, MODE_MANUAL, MOVE_STOP, true);
        robot_controller_tick(); stopped(); powered(true);
    }
    assert(robot_motor_trim(90, 100));
    accept(KIND_MOVE, MODE_MANUAL, MOVE_FORWARD, true);
    robot_controller_tick(); output(MOVE_FORWARD, 75);
    assert(duty[0] == 75 && duty[2] == 68); // RIGHT=OUT1/2; LEFT=OUT3/4.
    assert(!robot_motor_trim(80, 100)); // Do not retune a moving robot.
    accept(KIND_STOP, MODE_MANUAL, MOVE_STOP, true);
    assert(!robot_motor_trim(49, 100) && !robot_motor_trim(100, 151));
    assert(robot_motor_trim(150, 150));
    assert(motor_set(MOVE_FORWARD, 255) == ESP_OK);
    uint8_t left_duty, right_duty; motor_get_duties(&left_duty, &right_duty);
    assert(left_duty == 255 && right_duty == 255); // Saturate instead of overflowing 8-bit PWM.
    motor_stop();
    assert(robot_motor_trim(100, 100));
    accept(KIND_MOVE, MODE_MANUAL, MOVE_BACKWARD, true);
    robot_controller_tick(); output(MOVE_BACKWARD, 75);
    now += 300001; fresh_sensor(true, 100);
    robot_controller_tick(); stopped();
    accept(KIND_MOVE, MODE_MANUAL, MOVE_BACKWARD, true);
    robot_controller_tick(); stopped(); // Refresh cannot bypass the blind-motion burst limit.
    accept(KIND_STOP, MODE_MANUAL, MOVE_STOP, true);
    accept(KIND_MOVE, MODE_MANUAL, MOVE_FORWARD, true);
    robot_controller_tick(); output(MOVE_FORWARD, 75);
    now += 700001; fresh_sensor(true, 100);
    robot_watchdog_tick(); stopped();
    powered(true);
    assert(!robot_needs_reset());
    // A borrowed Manual robot stays powered while its old command is absent/expired.
    now += 5000000; fresh_sensor(true, 100);
    robot_idle(); robot_controller_tick(); stopped(); powered(true);
    // The next fresh Manual command works after an ordinary dead-man expiry.
    accept(KIND_MOVE, MODE_MANUAL, MOVE_FORWARD, true);
    robot_controller_tick(); output(MOVE_FORWARD, 75);
    accept(KIND_MODE, MODE_AUTO, MOVE_STOP, false);
    robot_controller_tick(); stopped(); powered(true); // Mode handoff stops PWM, keeps power.
    assert(relay_off_edges == power_cuts); // No relay cycling on STOP, idle, TTL or mode changes.
    assert(robot_ack_commit(&command, robot_revision()));
    robot_controller_tick(); output(MOVE_FORWARD, 75);
    fresh_sensor(true, 25); robot_controller_tick(); output(MOVE_FORWARD, 30);
    accept(KIND_KEEPALIVE, MODE_AUTO, MOVE_STOP, true);
    robot_controller_tick(); output(MOVE_FORWARD, 30);
    config.allow_blind_manual = false; // Auto backup is the requested recovery, independent of Manual opt-in.
    auto_reference_regressions();
    config.allow_blind_manual = true;
    fresh_sensor(false, 0); robot_watchdog_tick(); stopped();
    powered(false);
    assert(robot_needs_reset());
    robot_new_session(command.sequence, command.generation);
    fresh_sensor(true, 100);
    robot_borrow_update(command.lease_id);
    accept(KIND_MODE, MODE_AUTO, MOVE_STOP, true);
    robot_controller_tick(); output(MOVE_FORWARD, 75);
    now += 3000001; fresh_sensor(true, 100);
    robot_watchdog_tick(); stopped();
    powered(false);
    assert(robot_needs_reset()); // Persistent borrowing never makes Auto permits infinite.
    // Re-handshake fences old Auto; only a new Manual handoff/move can drive again.
    robot_new_session(command.sequence, command.generation);
    fresh_sensor(true, 100);
    robot_borrow_update(command.lease_id);
    accept(KIND_MODE, MODE_MANUAL, MOVE_STOP, true);
    accept(KIND_MOVE, MODE_MANUAL, MOVE_FORWARD, true);
    robot_controller_tick(); output(MOVE_FORWARD, 75);
    robot_borrow_update(NULL); stopped(); powered(false);
    robot_snapshot_t returned; robot_snapshot(&returned); assert(!returned.borrowed);
    const char *new_lease = "66666666-6666-4666-8666-666666666666";
    robot_borrow_update(new_lease); robot_controller_tick(); stopped(); powered(true);
    ++command.sequence; command.deadline_us = now + 700000;
    assert(robot_observe(command.sequence, command.generation));
    assert(robot_accept(&command) == ACK_REJECTED); // Old borrow cannot control the next renter's supply.
    memcpy(command.lease_id, new_lease, UUID_LEN);
    accept(KIND_MODE, MODE_MANUAL, MOVE_STOP, true);
    accept(KIND_MOVE, MODE_MANUAL, MOVE_FORWARD, true);
    robot_controller_tick(); output(MOVE_FORWARD, 75);
    fail_driver = true;
    accept(KIND_MOVE, MODE_MANUAL, MOVE_BACKWARD, true);
    robot_controller_tick(); stopped();
    powered(false);
    assert(robot_hardware_fault());
    puts("Runtime assertions passed: four GPIO/PWM directions, STOP/resume, TTL, Auto ACK, sensor and driver fail-safe");
    return 0;
}
