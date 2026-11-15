#pragma once
#include <stdbool.h>
#include <stdint.h>

#define UUID_LEN 37
#define MAX_SEQUENCE UINT64_C(9007199254740991)
typedef enum { MODE_MANUAL, MODE_AUTO } robot_mode_t;
typedef enum { MOVE_STOP, MOVE_FORWARD, MOVE_BACKWARD, MOVE_LEFT, MOVE_RIGHT } movement_t;
typedef enum { KIND_MOVE, KIND_STOP, KIND_MODE, KIND_KEEPALIVE } command_kind_t;
typedef enum { OBS_CLEAR, OBS_BLOCKED, OBS_SENSOR_ERROR } obstacle_t;
typedef enum { ACK_RECEIVED, ACK_APPLIED, ACK_REJECTED, ACK_FAILED } ack_status_t;

typedef struct {
    char id[UUID_LEN], robot_id[UUID_LEN], lease_id[UUID_LEN];
    uint64_t sequence, generation;
    command_kind_t kind;
    robot_mode_t mode;
    movement_t direction;
    int64_t deadline_us;
    bool safe_handoff;
} command_t;

typedef struct {
    bool valid, settling;
    float distance_cm;
    int angle;
    int64_t at_us;
} sensor_reading_t;

typedef struct {
    robot_mode_t mode;
    movement_t movement;
    obstacle_t obstacle;
    sensor_reading_t sensor;
    bool buzzer, relay, authorized, needs_reset;
    uint64_t sequence, generation, applied_sequence;
    int64_t deadline_us;
} robot_snapshot_t;

const char *mode_name(robot_mode_t mode);
const char *movement_name(movement_t movement);
const char *obstacle_name(obstacle_t obstacle);
const char *ack_name(ack_status_t ack);
