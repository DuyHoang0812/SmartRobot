#include "robot.h"
#include "protocol.h"
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

void console_task(void *argument)
{
    (void)argument;
    char line[64];
    for (;;) {
        if (!fgets(line, sizeof(line), stdin)) { clearerr(stdin); vTaskDelay(pdMS_TO_TICKS(100)); continue; }
        line[strcspn(line, "\r\n")] = 0;
        if (!strcmp(line, "relay on") || !strcmp(line, "relay off") || !strcmp(line, "relay toggle")) {
            puts(robot_relay_control(line + 6) ? "Relay updated" : "Relay denied: enable relay_console; robot must be stopped and connected");
        } else if (!strcmp(line, "status")) {
            robot_snapshot_t r; robot_snapshot(&r);
            printf("Mode=%s output=%s obstacle=%s buzzer=%s relay=%s\n", mode_name(r.mode), movement_name(r.movement),
                obstacle_name(r.obstacle), r.buzzer ? "on" : "off", r.relay ? "on" : "off");
        } else if (line[0]) puts("Commands: status | relay on | relay off | relay toggle");
    }
}
