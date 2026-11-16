#pragma once
#include "config.h"
#include "types.h"
#include "esp_err.h"

esp_err_t robot_init(const robot_config_t *config);
void robot_link_lost(void);
void robot_fault(bool new_session);
void robot_command_conflict(void);
const char *robot_reset_reason(void);
void robot_idle(void);
void robot_duplicate_deadline(const command_t *command);
bool robot_needs_reset(void);
bool robot_hardware_fault(void);
uint32_t robot_revision(void);
void robot_new_session(uint64_t sequence, uint64_t generation);
bool robot_observe(uint64_t sequence, uint64_t generation);
void robot_poll_alive(int64_t now_us);
void robot_heartbeat_alive(int64_t deadline_us);
void robot_borrow_update(const char *lease_id);
ack_status_t robot_accept(const command_t *command);
bool robot_ack_commit(const command_t *command, uint32_t revision);
void robot_snapshot(robot_snapshot_t *snapshot);
void robot_controller_tick(void);
void robot_watchdog_tick(void);
void robot_servo_pose(int *angle, int64_t *changed_us);
void robot_sensor_publish(sensor_reading_t sample, int64_t pose_at_start);
bool robot_relay_control(const char *operation);
bool robot_motor_trim(float left_percent, float right_percent);
bool robot_auto_configure(uint32_t clearance_cm, uint32_t backup_ms, uint32_t left_ms, uint32_t right_ms);
