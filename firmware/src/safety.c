#include "robot_internal.h"
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

void safety_tick_locked(robot_runtime_t *r, int64_t now)
{
    if (r->hardware_fault) { robot_invalidate_locked(r, true); return; }
    if ((r->poll_deadline_us && now >= r->poll_deadline_us)
        || (r->heartbeat_deadline_us && now >= r->heartbeat_deadline_us)) {
        robot_invalidate_locked(r, true); // Also de-energize a locally enabled relay while idle.
        return;
    }
    if (!r->public.authorized) return;
    if (now >= r->public.deadline_us || now >= r->heartbeat_deadline_us || now >= r->poll_deadline_us) {
        bool rearm = r->public.mode == MODE_AUTO || now >= r->heartbeat_deadline_us || now >= r->poll_deadline_us;
        robot_invalidate_locked(r, rearm);
        return;
    }
    sensor_reading_t *s = &r->public.sensor;
    if ((!s->valid || now - s->at_us > SENSOR_MAX_AGE_US) && !s->settling) {
        robot_stop_locked(r, true);
        r->inhibited_sequence = r->processed_sequence;
        if (r->public.mode == MODE_AUTO) robot_invalidate_locked(r, true);
    }
    if (r->public.movement == MOVE_FORWARD &&
        (!robot_center_fresh(r, now) || s->distance_cm < STOP_CM)) {
        robot_stop_locked(r, false);
        r->inhibited_sequence = r->processed_sequence;
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
