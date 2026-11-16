#include "robot_internal.h"
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

void safety_tick_locked(robot_runtime_t *r, int64_t now)
{
    if (r->hardware_fault) { robot_reset_locked(r, "actuator_driver"); return; }
    if ((r->poll_deadline_us && now >= r->poll_deadline_us)
        || (r->heartbeat_deadline_us && now >= r->heartbeat_deadline_us)) {
        robot_reset_locked(r, r->poll_deadline_us && now >= r->poll_deadline_us
                              ? "command_poll_timeout" : "heartbeat_timeout");
        return;
    }
    if (!r->public.authorized) return;
    if (now >= r->public.deadline_us || now >= r->heartbeat_deadline_us || now >= r->poll_deadline_us) {
        bool rearm = r->public.mode == MODE_AUTO || now >= r->heartbeat_deadline_us || now >= r->poll_deadline_us;
        if (rearm) robot_reset_locked(r, "auto_permit_expired");
        else robot_invalidate_locked(r, false);
        return;
    }
    sensor_reading_t *s = &r->public.sensor;
    // An unobservable SIDE is not a clear path. While stationary, Auto can time out
    // that scan and examine the other side instead of rebooting the whole session.
    bool side_scan = r->public.mode == MODE_AUTO && r->public.movement == MOVE_STOP
        && (r->phase == AUTO_LEFT || r->phase == AUTO_RIGHT);
    if ((!s->valid || now - s->at_us > SENSOR_MAX_AGE_US) && !s->settling && !side_scan) {
        robot_stop_locked(r, false);
        if (r->public.mode == MODE_MANUAL) r->inhibited_sequence = r->processed_sequence;
        if (r->public.mode == MODE_AUTO) robot_reset_locked(r, s->valid ? "sensor_stale" : "sensor_invalid");
    }
    if (r->public.movement == MOVE_FORWARD &&
        (!robot_center_fresh(r, now) || s->distance_cm < STOP_CM)) {
        robot_stop_locked(r, false);
        // Manual blocks replay of this MOVE. Auto keeps its own recovery phase;
        // the front-distance guard does not apply to BACKWARD or pivot output.
        if (r->public.mode == MODE_MANUAL) r->inhibited_sequence = r->processed_sequence;
    }
}

void safety_task(void *argument)
{
    (void)argument;
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    for (;;) {
        robot_watchdog_tick();
        ESP_ERROR_CHECK(esp_task_wdt_reset());
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}
