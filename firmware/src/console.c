#include "robot.h"
#include "protocol.h"
#include <stdio.h>
#include <string.h>
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

void console_task(void *argument)
{
    const robot_config_t *config = argument;
    char line[64];
    for (;;) {
        if (!fgets(line, sizeof(line), stdin)) { clearerr(stdin); vTaskDelay(pdMS_TO_TICKS(100)); continue; }
        line[strcspn(line, "\r\n")] = 0;
        float left, right; char extra;
        for (char *p = line; *p; ++p) if (*p == ',') *p = '.';
        if (!strcmp(line, "auto reference")) {
            puts(robot_auto_configure(DEFAULT_AUTO_CLEARANCE_CM, DEFAULT_AUTO_BACKUP_MS,
                DEFAULT_AUTO_TURN_MS, DEFAULT_AUTO_TURN_MS)
                ? "Auto ver2_6 applied: clearance=15cm backup=400ms turn_left=400ms turn_right=400ms; use 'auto save' to persist"
                : "Auto configuration denied: select Manual and release movement buttons first");
        } else if (!strcmp(line, "auto save")) {
            robot_snapshot_t r; robot_snapshot(&r);
            if (!robot_auto_configure(r.auto_clearance_cm, r.auto_backup_ms, r.auto_turn_left_ms, r.auto_turn_right_ms))
                puts("Auto configuration denied: select Manual and release movement buttons first");
            else puts(config_save_auto(r.auto_clearance_cm, r.auto_backup_ms, r.auto_turn_left_ms, r.auto_turn_right_ms) == ESP_OK
                ? "Auto configuration saved to NVS" : "Auto configuration save failed");
        } else if (!strcmp(line, "trim save")) {
            robot_snapshot_t r; robot_snapshot(&r);
            if (!robot_motor_trim(r.left_motor_percent, r.right_motor_percent))
                puts("Trim denied: select Manual and release movement buttons first");
            else puts(config_save_motor_trim(r.left_motor_percent, r.right_motor_percent) == ESP_OK
                ? "Motor trim saved to NVS" : "Motor trim save failed");
        } else if (sscanf(line, "trim %f %f %c", &left, &right, &extra) == 2) {
            if (robot_motor_trim(left, right))
                printf("Trim applied: LEFT=%.1f%% RIGHT=%.1f%%; use 'trim save' to persist\n", left, right);
            else puts("Trim denied: 50..150 percent; Manual and stopped required");
        } else if (!strcmp(line, "relay on") || !strcmp(line, "relay off") || !strcmp(line, "relay toggle")) {
            puts(robot_relay_control(line + 6) ? "Motor power OFF; current intent cancelled"
                : "Relay supplies motors: power is managed automatically by validated drive commands");
        } else if (!strcmp(line, "status")) {
            robot_snapshot_t r; robot_snapshot(&r);
            printf("Mode=%s output=%s obstacle=%s buzzer=%s relay=%s\n", mode_name(r.mode), movement_name(r.movement),
                obstacle_name(r.obstacle), r.buzzer ? "on" : "off", r.relay ? "on" : "off");
            printf("Motors=%d blind=%d PWM=%u/255 full=%u slow=%u turn=%u authorized=%d reset=%d borrowed=%d\n",
                config->motors_enabled, config->allow_blind_manual, r.motor_duty,
                config->full_speed, config->slow_speed, config->turn_speed, r.authorized, r.needs_reset, r.borrowed);
            printf("LEFT: OUT3/4 duty=%u trim=%.1f%%; RIGHT: OUT1/2 duty=%u trim=%.1f%%\n",
                r.left_motor_duty, r.left_motor_percent, r.right_motor_duty, r.right_motor_percent);
            printf("Auto clearance=%lucm backup=%lums turn_left=%lums turn_right=%lums\n",
                (unsigned long)r.auto_clearance_cm, (unsigned long)r.auto_backup_ms,
                (unsigned long)r.auto_turn_left_ms, (unsigned long)r.auto_turn_right_ms);
            printf("Seq=%llu applied=%llu gen=%llu TTL=%lldms sensor_valid=%d settling=%d angle=%d distance=%.1fcm age=%lldms\n",
                (unsigned long long)r.sequence, (unsigned long long)r.applied_sequence,
                (unsigned long long)r.generation, (long long)((r.deadline_us-esp_timer_get_time())/1000),
                r.sensor.valid, r.sensor.settling, r.sensor.angle, r.sensor.distance_cm,
                (long long)((esp_timer_get_time()-r.sensor.at_us)/1000));
        } else if (line[0]) puts("Commands: status | trim LEFT% RIGHT% | trim save | auto reference | auto save | relay off");
    }
}
