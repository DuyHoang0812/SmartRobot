#include "hardware.h"
#include "board.h"
#include "driver/gpio.h"

esp_err_t outputs_init(void)
{
    // Preload safe levels before enabling output: relay active-low, Buzzer active-high.
    gpio_set_level(PIN_RELAY, 1);
    gpio_set_level(PIN_BUZZER, 0);
    gpio_config_t c = {.pin_bit_mask = (1ULL << PIN_RELAY) | (1ULL << PIN_BUZZER),
        .mode = GPIO_MODE_OUTPUT, .intr_type = GPIO_INTR_DISABLE};
    return gpio_config(&c);
}
void buzzer_set(bool on) { gpio_set_level(PIN_BUZZER, on ? 1 : 0); }
void relay_set(bool on) { gpio_set_level(PIN_RELAY, on ? 0 : 1); }
