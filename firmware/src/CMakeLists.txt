
idf_component_register(
    SRCS "main.c" "config.c" "motor.c" "servo.c" "outputs.c" "sensor.c"
         "robot.c" "manual.c" "auto.c" "safety.c" "wifi.c" "http.c"
         "protocol.c" "device.c" "telemetry.c" "console.c"
    INCLUDE_DIRS "."
    REQUIRES esp_wifi esp_event esp_netif nvs_flash esp_http_client esp_timer
             esp_driver_gpio esp_driver_ledc esp_system esp_hw_support lwip mbedtls
)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Werror)
