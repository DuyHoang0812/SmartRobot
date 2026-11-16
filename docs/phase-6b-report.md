# Phase 6B — Complete ESP32 Firmware

Cập nhật firmware **6b-2**: sửa STOP thừa ở frontend và xử lý ACK409 superseded; firmware
gửi final ACK trực tiếp (RECEIVED tùy chọn). Chi tiết/bằng chứng kiểm thử mới ở
[báo cáo bản vá](fixes/control-lease-ack-conflict.md). Kết quả build và mô tả ACK bên dưới
ghi nhận bản triển khai 6b-1 ban đầu.

Triển khai ngày 16/11/2026 trên project PlatformIO người dùng đã setup. Đã đọc toàn bộ
ver2_6_esp32.ino, esp32-device-api.md, robot-control-protocol.md, phase-6a-report.md,
PlatformIO/CMake/sdkconfig và kiểm tra implementation Device API hiện hành.
Không tạo lại project, không đổi framework, không sửa backend/frontend hoặc Device API.

## Phần đã triển khai

Toàn bộ firmware C/ESP-IDF native đã có: Station Wi-Fi/reconnect, HTTPS/HTTP LAN, NVS config,
boot UUID/session, heartbeat, polling/ordering/TTL, RECEIVED/APPLIED/REJECTED/FAILED ACK,
telemetry; L298N, HC-SR04, servo, Buzzer, relay; Manual/Auto state machines, safety watchdog
độc lập HTTP và UART console. Không có Arduino dependency, ESP32 web server, MQTT hoặc
Robot Simulator. Không flash, mở serial monitor hay kích hoạt động cơ trong quá trình làm.

## GPIO và linh kiện từ code mẫu

| Linh kiện | GPIO | Chính sách |
| --- | --- | --- |
| L298N IN1, IN2 | 19, 21 | Giữ thứ tự/chiều quay mẫu |
| L298N IN3, IN4 | 5, 18 | Giữ thứ tự/chiều quay mẫu |
| HC-SR04 TRIG, ECHO | 27, 14 | Trigger10µs, ISR đo echo; cần chuyển mức ECHO xuống3.3V |
| Servo | 13 | 50Hz, 500–2400µs; 0° trái, 90° giữa, 180° phải |
| Buzzer | 12 | Active-high, cảnh báo vật cản; Auto warning beep100ms |
| Relay | 26 | Active-low, preloadHIGH/OFF trước output, không suy luận là nguồn motor |

Đối chiếu tự động cả9 chân với file .ino đạt. GPIO5/GPIO12 boot strapping và điện trở giữ
mức an toàn/nguồn motor/servo cần xác minh trên xe; phần mềm không kiểm soát mức chân
trước bootloader/reset. Servo không có feedback vị trí, cần xác nhận cơ khí thực tế.

Motor truth table IN1/IN2/IN3/IN4:

| Trạng thái | IN1 | IN2 | IN3 | IN4 |
| --- | --- | --- | --- | --- |
| FORWARD | PWM | 0 | PWM | 0 |
| BACKWARD | 0 | PWM | 0 | PWM |
| TURN_LEFT | 0 | PWM | PWM | 0 |
| TURN_RIGHT | PWM | 0 | 0 | PWM |
| STOPPED | 0 | 0 | 0 | 0 |

Giữ PWM trên IN1–IN4 như file mẫu, 1kHz/8-bit, duty75/30/75 mặc định (không phải phần
trăm). Không gán chân ENA/ENB mới, không giả định có PWM ở ENA/ENB. Phải kiểm tra jumper/
enable thực tế của L298N. Servo timer1 tách motor timer0; dùng5 LEDC channels.

Relay giữ tính chất tải on/off độc lập, điều khiển thủ công qua UART `relay on/off/toggle`
khi bật relay_console, motor đứng yên và kết nối còn mới. Không thêm trường hoặc endpoint
relay vào protocol chưa có. Boot/fail-safe cắt relay; không tự đóng relay khi nhận MOVE.

## Modules

| Module | Trách nhiệm |
| --- | --- |
| config.c/h | Nạp robot_cfg NVS, xác thực URL/headers/arming/timing, không hardcode secret |
| board.h | Mapping cố định, ngưỡng/timing phần cứng |
| motor.c | GPIO/LEDC IN PWM, chuyển hướng về0 trước đổi cực, xử lý lỗi driver |
| servo.c | PWM50Hz/timer riêng, góc theo mẫu |
| outputs.c | Buzzer active-high/relay active-low, safe boot levels |
| sensor.c | GPIO edge ISR/notification, timeout/stale/invalid fail-safe, task riêng |
| robot.c/h, robot_internal.h | Mutex, fence/intent, snapshots và quản lý output duy nhất |
| manual.c | Bốn hướng, obstacle latch và burst lùi/quay không gia hạn bằng refresh |
| auto.c | DRIVE/SCAN LEFT/SCAN RIGHT/CENTER/TURN/WAIT FRONT/HALT, không delay dài |
| safety.c | Watchdog20ms độc lập HTTP + ESP-IDF task watchdog5s |
| wifi.c/h | Station RAM credentials, reconnect1–30s, disconnect epoch và SNTP |
| http.c/h | HTTP client keep-alive, TLS CA/hostname, timeout, bounded JSON buffer, no redirects |
| protocol.c/h, types.h | UTC parsing, IDs/seq/gen/lease/TTL validation, JSON ACK, enum contracts |
| device.c | Auth/session lifecycle, heartbeat/poll/ACK/telemetry scheduling và recovery |
| telemetry.c | Sensor/output snapshot → Device JSON, null khi không có dữ liệu hợp lệ |
| console.c | Status/relay cục bộ, không in credential |
| main.c | Safe boot/task creation; không gom business logic |

## Manual/Auto và safety

Manual Forward cần mẫu sensor mới <=250ms, đã ổn định ở hướng giữa. Khoảng cách <15cm
dừng/còi; lỗi/timeout/out-of-range/stale dừng. Không tiếp tục cùng sequence khi vật cản
được dỡ, chỉ nhận lệnh mới còn hạn. No echo không còn bị coi là999cm đường trống.

Vì chỉ có sensor trước, Lùi/Trái/Phải Manual cần explicit allow_blind_manual và đợt tối đa
300ms (config50–400ms), không gia hạn bằng MOVE refresh; nhả nút/STOP reset đợt. Mặc định
chưa bật các hướng mù, không tự nhận định phía sau/bên hông an toàn.

Auto >=40cm chạy duty thường, 15–<40cm chậm, <15cm dừng/quét. Hai phía đo sau settle600ms,
chọn phía xa hơn nếu >=40cm, center rồi quay tối đa400ms. Sau quay cần mẫu trước mặt mới
trước chạy tiếp. Không có hướng phù hợp thì HALT; sensor lỗi thì dừng và re-handshake.
Không port bước lùi400ms hoặc tự lùi khi khoảng cách ít đổi3s từ mẫu: các hành vi đó
không chứng minh phía sau an toàn và mâu thuẫn fail-safe với dữ liệu cảm biến hiện có.

Core1: controller10ms, sensor task đo bounded, watchdog20ms priority10. Core0: HTTP task,
Wi-Fi native events. Motor/servo/relay runtime ghi trong cùng mutex; HTTP/echo waits ở
ngoài mutex. Sensor ISR chỉ ghi pulse timestamps/notify, không điều khiển motor.

Rà soát transitions: STOP/generation/mode/lease đổi dừng trước nhận intent; Auto→Manual
hủy FSM và chỉ safe ACK khi outputSTOPPED. Mode mới chờ APPLIED receipt trước chạy Auto.
TTL/authorization/heartbeat/poll freshness1s hoặc Wi-Fi/HTTP error vô hiệu hóa local intent.
KEEPALIVE kiểm tra permit cũ ngay trong critical section, không chờ tick watchdog để
chặn late refresh. Duplicate không reapply/extend deadline. Auto timeout/fault cần UUID/
session mới, không resume từ cache. Lỗi driver latching không tạo vòng re-auth liên tục.

Các chu kỳ trên là thiết kế phần mềm, **chưa đo được latency dừng vật lý hoặc scheduler
jitter trên ESP32**. Motor dừng thực tế còn phụ thuộc mạch, tải, nguồn và điện trở giữ mức.
Không có encoder: actual_movement phản ánh output driver, không chứng minh bánh đang quay.

## Tương thích Device API

Không đổi schema/backend. Credential headers độc lập JWT; URL không có secret. Session
UUID kiểm tra ở response, boot UUID ngẫu nhiên sau Wi-Fi; auth retry giữ UUID. Heartbeat/
sample counters boot-local, seq/gen server high-water không reset tùy ý. Heartbeat không
gia hạn motor. Firmware không thực thi command không auth/null/expired/sai identity/fence.

Deadline = monotonic request-start + min(authorization_expires_at - server_time, TTL cap)
-20ms; tương đương trừ toàn bộ RTT khỏi thời gian còn lại tại lúc nhận. Parse UTC Z/+00:00
và microseconds, không dùng đồng hồ wall-clock cho motor watchdog. TLS vẫn cần giờ SNTP.

ACK RECEIVED trước local apply, APPLIED/REJECTED/FAILED sau validation. Safe handoff báo
actual_mode và STOPPED đúng schema; command_sequence_applied chỉ gửi sau ACK200 đã kiểm
tra receipt. APPLIED không chứng minh chuyển động cơ học. Khi kết quả mạng không chắc
chắn, firmware dừng và re-auth thay vì phục hồi lệnh đang chạy. Telemetry429 giữ body/
counter, tôn trọng Retry-After; fence đổi bỏ sample cũ. Cảm biến khi servo chưa ổn định
không xuất distance hợp lệ; SENSOR_ERROR/null tạm thời không được dùng để chạy tiến.

HTTPS xác minh CA/hostname, không skip check hoặc follow redirects mang credential.
HTTP development cần opt-in hai phía và IP LAN số/private, không hỗ trợ public HTTP.
Buffer response8192 bytes, malformed JSON/status/identity đều fail-safe. Không log payload.

## Kết quả kiểm chứng thực tế

| Kiểm tra | Kết quả |
| --- | --- |
| `pio run` trên project esp32dev/ESP-IDF6.1.0 | SUCCESS, lần cuối7.72s |
| Compile/link C modules `-Wall -Wextra -Werror` | Pass |
| Static RAM | 48524 / 327680 bytes (14.8%); chưa gồm heap/task/TLS runtime |
| App flash dùng | 1021905 / 3145728 bytes (32.5%) |
| Header firmware | 4MB, script check_board pass |
| GPIO .ino ↔ board.h | Cả9 chân khớp |
| Partition binary decode | App3MB + robot_cfg64K đúng offsets, nằm trong4MB |
| esptool image_info | Image checksum/hash valid (kiểm tra file, không mở serial) |
| Host C codec với AddressSanitizer/UBSan | Pass: UTC/IDs/seq/gen/TTL/4 directions/STOP/serializers |
| Firmware JSON → Pydantic schemas backend thật | RECEIVED/APPLIED/REJECTED/FAILED và telemetry pass |
| Python provisioning tests | 5 passed; image64K/0600, no secret output, CSV cleanup |
| Ruff tools/tests firmware | Pass; 4 Python files formatted |
| Device API + HTTP/WebSocket Uvicorn thật, DB test | 43 passed,26.38s |
| Flash/upload/monitor/motor activation | Không thực hiện |
| FreeRTOS FSM/watchdog trên ESP32/xe thật | Chưa kiểm chứng; đã compile và rà soát mã |

Host tests chỉ kiểm thử hàm codec/cấu hình; không tạo GPIO driver stubs, mock backend,
robot emulator hoặc simulator. Không dùng host tests làm bằng chứng phần cứng chạy được.
Backend/frontend không đổi; không chạy lại toàn bộ web tests vì không sửa web source.

Lỗi trong quá trình làm: sandbox cache PlatformIO cần quyền ghi đúng môi trường hiện có;
include sockets ESP-IDF được bổ sung cho inet_pton; host include cJSON nằm trong thư mục
managed cJSON/cJSON; sửa signedness assertion. Môi trường IDF chưa có công cụ NVS chính
thức nên đã bổ sung esp-idf-nvs-partition-gen0.3.0, pin trong tools/requirements.txt.
Đã sửa và kiểm thử lại các bước bị lỗi. Không còn compile/link/test failures.
SDK6.1.0 có NOTE Kconfig default0 cho một số bool Bluetooth/FATFS; không phải warning C
của firmware, không tự sửa package framework. Các subsystem này không dùng bởi app.

## File thay đổi

Giữ và bổ sung vào project PlatformIO/CMake đã có:

```text
.gitignore
README.md
firmware/platformio.ini
firmware/sdkconfig.esp32dev
firmware/src/CMakeLists.txt
firmware/src/main.c
firmware/ver2_6_esp32.ino
```

Thêm source/header modules nêu ở bảng Modules, `firmware/src/idf_component.yml`,
`firmware/dependencies.lock`, `firmware/partitions.csv`, `firmware/sdkconfig.defaults`,
`firmware/device.example.json`, `firmware/README.md`, `firmware/test/protocol_test.c`,
`firmware/test/test_provision.py`, `firmware/tools/provision.py`, `check_board.py`,
`check_contract.py`, `tools/requirements.txt` và báo cáo này. Giữ root CMakeLists.txt,
không chạy pio project init. Project ban đầu có một số file untracked; không coi chúng
là project mới do agent tạo. File .ino vẫn giữ mapping/algorithm tham khảo, chỉ xóa các
giá trị Wi-Fi credential cũ khỏi source, không dùng để build firmware mới.

## Cấu hình, upload và monitor

Hướng dẫn chi tiết: [firmware/README.md](../firmware/README.md).

Điền device.local.json đã gitignore: Wi-Fi SSID/password, URL laptop `/api/v1/devices`,
Device ID/secret do Admin cấp, CA PEM/hostname, NTP; timing/speeds/arming/relay policy.
Mặc định motors_enabled=false, allow_blind_manual=false, relay_console=false.
NVS chứa credential thiết bị cần dùng khi gửi HTTP nên không thể thay bằng hash MCU;
không nhúng vào app image/source, file/image0600 và không in ra CLI. Flash NVS chưa mã
hóa; chưa cấu hình flash encryption/secure boot/eFuse, cần quy trình sản xuất riêng.

Operator tự chạy, khi nguồn motor/tải relay đã ngắt và bánh được kê:

```bash
cd firmware
pio run
umask 077
cp device.example.json device.local.json
chmod 600 device.local.json
# Điền bằng editor; chỉ enable motors sau khi kiểm tra phần cứng.
IDF_PYTHON="$HOME/.platformio/penv/.espidf-6.1.0/bin/python"
"$IDF_PYTHON" -m pip install -r tools/requirements.txt
python3 tools/provision.py
pio run -t upload --upload-port /dev/ttyUSB0
pio pkg exec -p tool-esptoolpy -- esptool.py --chip esp32 --port /dev/ttyUSB0 \
  --baud 460800 write_flash 0x310000 secrets/robot_cfg.bin
pio device monitor --port /dev/ttyUSB0 --baud 115200
```

Agent chỉ chạy build/image-info; chưa chạy ba lệnh serial/upload cuối. Có thể thay cổng
thiết bị phù hợp. Không erase toàn chip/volume/database. Nạp app không ghi robot_cfg.

## Checklist thử trên xe thật

1. Giữ nguồn motor/tải relay ngắt, kiểm tra9 chân/ECHO divider/common GND/strapping,
   phân cực relay, ENA/ENB jumpers và nguồn servo. Servo chuyển giữa các góc cần không kẹt.
2. Provision motor chưa armed; boot phải relayOFF/motorSTOP. Xem log không chứa secret,
   kiểm tra Station, SNTP/TLS hoặc HTTP LAN opt-in, Admin thấy Online sau heartbeat.
3. Dùng tài khoản có lease, xác nhận Manual safe ACK. Khi motors_enabled=false, MOVE bị
   REJECTED và lease đóng. Chỉ sau khi sơ đồ đã kiểm tra mới enable, cấp lại NVS và reset.
4. Kê bánh, có người ngắt nguồn vật lý: thử từng hướng, so chiều bánh với truth table;
   nhả/cancel/blur web phải dừng. Với blind opt-in, giữ liên tục không vượt burst cap;
   không xem không gian sau/bên là đã có cảm biến kiểm tra.
5. Đưa vật cản <15cm trước khi/đang tiến: outputSTOP/còi/telemetryBLOCKED; dỡ vật cản không
   chạy lại sequence cũ. Cần MOVE mới hợp lệ. Rút ECHO/tắt sensor phải SENSOR_ERROR/null
   và dừng, không coi no echo là đường trống. Không đưa5V trực tiếp vào GPIO14.
6. Auto trên vùng trống có kiểm soát: >=40cm bình thường,15–<40cm chậm; <15cm dừng/quét,
   chọn phía phù hợp/turn400ms, đọc trước mới trước chạy tiếp; hai phía bị chặn thì dừng.
   Thử mất sensor giữa scan/turn; Auto→Manual phải hủy FSM trước mở Manual.
7. Khi đang điều khiển: tắt Wi-Fi, dừng FastAPI, gây timeout, logout, release, disable,
   rotate credential, ngừng renew/KEEPALIVE và reset ESP32. Đo thời gian dừng thực, xác
   nhận reconnect không resume lệnh/Auto cũ; session/boot mới cần nhận quyền lại.
8. Thử relay bằng UART khi đã biết tải thực; off lúc boot/lỗi/mất kết nối. Không tự coi
   relay là công tắc nguồn motor; chỉ cho tải sau khi phân cực/wiring được xác minh.
9. Theo dõi heap/stack/TLS, jitter sensor, nguồn sụt/brownout và độ bền nhiều phiên/multi-robot
   trên mạng thật. Chưa có kiểm chứng nào về các số đo vật lý này trong Phase 6B hiện tại.

Chưa xác minh: hướng/lực động cơ thực, PWM phù hợp module L298N thực, hành trình servo,
Buzzer active thực, relay tải nào, điện áp ECHO, noise/độ chính xác HC-SR04, lỗi sensor vẫn
cho pulse hợp lệ, khả năng phát hiện vật cản ở hông/sau, độ trễ braking/coast, brownout,
TLS/Wi-Fi trên ESP32 và latency watchdog trên xe. Phần mềm không thể phát hiện mọi sensor
lỗi vẫn tạo dữ liệu trông hợp lệ hoặc xác minh chuyển động nếu không có encoder.

Tất cả module được triển khai và build thành công; chờ operator cấu hình/flash và nghiệm
thu phần cứng. Không tự bắt đầu phase khác hoặc kích hoạt thiết bị.
