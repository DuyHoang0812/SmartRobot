#pragma once
// Exact wiring and electrical polarity from ver2_6_esp32.ino. No ENA/ENB GPIO exists.
#define PIN_IN1 19
#define PIN_IN2 21
#define PIN_IN3 5
#define PIN_IN4 18
#define PIN_TRIG 27
#define PIN_ECHO 14
#define PIN_SERVO 13
#define PIN_BUZZER 12
#define PIN_RELAY 26
#define SERVO_CENTER 90
#define SERVO_LEFT 0
#define SERVO_RIGHT 180
#define SERVO_SETTLE_US INT64_C(600000)
#define SENSOR_MAX_AGE_US INT64_C(250000)
#define STOP_CM 15.0f
#define WARN_CM 40.0f
