#pragma once
#include "robot.h"
#include "board.h"
#include "hardware.h"

typedef enum { AUTO_DRIVE, AUTO_LEFT, AUTO_RIGHT, AUTO_CENTER, AUTO_TURN, AUTO_FRONT, AUTO_HALT } auto_phase_t;
typedef struct {
    const robot_config_t *config;
    robot_snapshot_t public;
    command_t intent;
    bool ready, hardware_fault, blind_blocked;
    uint32_t revision;
    uint64_t processed_sequence, inhibited_sequence;
    int angle;
    int64_t servo_changed_us, heartbeat_deadline_us, poll_deadline_us, blind_started_us;
    auto_phase_t phase;
    float left_cm, right_cm;
    movement_t turn;
    int64_t phase_deadline_us;
} robot_runtime_t;

// Called only while robot.c owns its single mutex; no task/HTTP waits in these functions.
void robot_stop_locked(robot_runtime_t *r, bool outputs_off);
void robot_invalidate_locked(robot_runtime_t *r, bool reset);
bool robot_center_fresh(const robot_runtime_t *r, int64_t now);
void robot_angle_locked(robot_runtime_t *r, int angle, int64_t now);
movement_t manual_tick_locked(robot_runtime_t *r, int64_t now, uint8_t *speed);
movement_t auto_tick_locked(robot_runtime_t *r, int64_t now, uint8_t *speed);
void safety_tick_locked(robot_runtime_t *r, int64_t now);
