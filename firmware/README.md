# SmartRobot ESP32 — ESP-IDF / PlatformIO

Firmware C native cho project PlatformIO hiện có: esp32dev, ESP32-D0WD-V3, ESP-IDF 6.1.0,
Flash 4MB, UART 115200. Không dùng Arduino, web server ESP32, MQTT hoặc Robot Simulator.
Giao thức giữ nguyên [Device API](../docs/esp32-device-api.md) của Phase 6A.

## GPIO và động cơ

| Linh kiện | GPIO / cấu hình giữ từ ver2_6_esp32.ino |
| --- | --- |
| L298N IN1 / IN2 | 19 / 21 |
| L298N IN3 / IN4 | 5 / 18 |
| HC-SR04 TRIG / ECHO | 27 / 14 |
| Servo | 13, 50Hz, 500–2400µs, trái 0° / giữa 90° / phải 180° |
| Buzzer active-high | 12 |
| Relay active-low | 26, HIGH = OFF lúc khởi động |

Truth table IN1/IN2/IN3/IN4: Tiến PWM/0/PWM/0; Lùi 0/PWM/0/PWM;
Trái 0/PWM/PWM/0; Phải PWM/0/0/PWM; Dừng 0/0/0/0. Giữ chiều quay logic từ bản cũ.
PWM 1kHz/8-bit đặt **trên IN1–IN4**, như code mẫu; không tạo GPIO ENA/ENB. ENA/ENB phải
được enable đúng theo mạch/jumper thực tế. Firmware không có khả năng điều khiển độc lập
ENA/ENB hoặc cắt nguồn qua chân chưa nối. Servo dùng timer LEDC riêng 50Hz/16-bit.
Nguồn: [datasheet L298 của ST](https://www.st.com/resource/en/datasheet/l298.pdf).

ECHO HC-SR04 cần chia áp/level shifting xuống 3.3V như ghi chú của file mẫu. Kiểm tra nguồn
motor/servo, common GND và tải relay. GPIO5/GPIO12 liên quan boot strapping; firmware không
thể áp đặt mức chân trước boot/reset. Cần kiểm tra điện trở giữ mức an toàn trên mạch thật.

## Build

Từ `firmware/`:

```bash
pio run
```

Giữ platform `espressif32@7.1.1`, framework ESP-IDF 6.1.0. cJSON được quản lý bằng
`src/idf_component.yml` và `dependencies.lock`, pin `espressif/cjson 1.7.19~2` vì IDF 6
đã chuyển JSON sang managed component ([Espressif migration guide](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/migration-guides/release-6.x/6.0/protocols.html)).
Managed dependencies/build cache không cần commit; không khởi tạo project lần nữa.

Partition: NVS mặc định 0x9000/24K, PHY 0xf000/4K, app 0x10000/3MB,
`robot_cfg` 0x310000/64K. Header firmware là **4MB**, 3MB chỉ là giới hạn app partition.
Không có OTA trong bản này. Không dùng erase_flash để đổi cấu hình.

## Cấp cấu hình riêng bằng NVS

Firmware image không chứa Wi-Fi/password/Device Secret. Tạo file local đã được gitignore:

```bash
umask 077
cp device.example.json device.local.json
chmod 600 device.local.json
```

Điền bằng editor, không truyền secret qua CLI hoặc đưa vào logs:

- `wifi_ssid`, `wifi_password`: Wi-Fi Station. Mật khẩu rỗng chỉ cho AP mở; WPA2 >=8 bytes.
- `backend_url`: kết thúc chính xác `/api/v1/devices`, không slash cuối/query/userinfo.
  Ví dụ HTTPS `https://smartrobot.lan/api/v1/devices`. Đây là địa chỉ **laptop**, không
  phải localhost của ESP32. Dùng DHCP reservation/DNS ổn định.
- `device_id`, `device_secret`: Admin cấp riêng cho xe, secret chỉ hiện một lần. Rotate
  thì cập nhật NVS và reboot; không thay backend code.
- `ca_file`: đường dẫn PEM CA tính từ thư mục JSON (tối đa 3900 bytes). Rỗng dùng bundle
  CA công khai của ESP-IDF. Hostname/IP phải khớp certificate, luôn kiểm tra cert/hostname.
- `ntp_server`: mặc định pool.ntp.org, có thể dùng NTP LAN. HTTPS chờ giờ >=2024 trước
  authenticate; không bỏ kiểm tra certificate để tránh lỗi giờ.
- `allow_http_lan`: false mặc định. Chỉ LAN development mới bật true ở cả firmware và
  backend `DEVICE_ALLOW_INSECURE_HTTP`. Firmware yêu cầu URL IPv4 số thuộc mạng private;
  HTTP không dùng DNS/public IP, không mã hóa credential. Firewall chỉ cho LAN, không
  port-forward/public Internet. Production dùng HTTPS.
- `motors_enabled`: **false mặc định**. Chỉ bật true sau kiểm tra dây và kê bánh an toàn.
- `allow_blind_manual`: false mặc định vì không có cảm biến sau/bên. Để thử Lùi/Trái/Phải,
  operator phải kiểm tra không gian và chủ động bật true. Mỗi đợt mù tối đa
  `blind_manual_max_ms` (300ms mặc định, 50–400ms); refresh lệnh không kéo dài đợt đó,
  cần nhả nút/STOP hoặc mode handoff để mở đợt mới. Đây không phải bằng chứng phía sau an toàn.
- `full_speed` / `slow_speed` / `turn_speed`: giữ mặc định 75/30/75 trên thang duty 0–255;
  khoảng cho cấu hình 1–255, slow <= full. Không mặc định duty75 là 75%.
- `http_timeout_ms`: mặc định 250ms, 50–400ms. Auth/TLS ban đầu timeout5s khi xe dừng.
- `relay_console`: false mặc định; bật nếu cần thao tác relay qua UART cục bộ.

Cài công cụ NVS chính thức vào Python ESP-IDF hiện có (một lần):

```bash
IDF_PYTHON="$HOME/.platformio/penv/.espidf-6.1.0/bin/python"
"$IDF_PYTHON" -m pip install -r tools/requirements.txt
python3 tools/provision.py
```

`secrets/robot_cfg.bin` được tạo 64K/0600, CSV tạm được xóa, giá trị không in ra terminal.
Nếu PlatformIO ở thư mục khác, dùng `PLATFORMIO_CORE_DIR` hoặc `--idf-python <path>`.
Tool **chỉ tạo image**, không có thao tác flash/serial. `device.local.json`, `secrets/`,
`.pio/` đều gitignore. NVS này chưa mã hóa trên flash: bảo vệ file/thiết bị; flash encryption,
secure boot và khóa provisioning sản xuất cần quy trình phần cứng riêng, không tự ghi eFuse.

## Upload và monitor — operator tự thực hiện

Ngắt nguồn động cơ/tải relay trước lần nạp đầu, kê bánh, giữ servo không vướng cơ khí.
Các lệnh dưới đây **có flash thật**, agent chưa chạy chúng:

```bash
# Từ firmware/, chọn đúng cổng serial của thiết bị
pio run -t upload --upload-port /dev/ttyUSB0
pio pkg exec -p tool-esptoolpy -- esptool.py --chip esp32 \
  --port /dev/ttyUSB0 --baud 460800 write_flash 0x310000 secrets/robot_cfg.bin
pio device monitor --port /dev/ttyUSB0 --baud 115200
```

Tool esptool chạy qua môi trường PlatformIO để có pyserial. Nạp app thông thường không
ghi đè robot_cfg; cấp lại config chỉ ghi partition riêng. Nếu partition còn trắng hoặc
cấu hình sai, startup giữ motor/relay OFF và in lỗi chung, không in secret. Sau thay đổi
config cần reset. Không thử motor bằng upload command; điều khiển chỉ nhận từ backend lease.

Console: `status`, `relay on`, `relay off`, `relay toggle`. Relay vẫn là tải độc lập active-low
như mẫu cũ, không tự suy luận là nguồn motor. On/toggle yêu cầu relay_console=true, output
motor đang STOPPED và polling còn kết nối; Off luôn được chấp nhận. Mất mạng/watchdog/
thu hồi điều khiển trả relay OFF. Không tạo endpoint relay mới trong Device API/backend.
Không có AP/web server/điều khiển relay qua web trên ESP32 trong kiến trúc Station hiện tại.

## Điều khiển, Auto và watchdog

Manual bốn hướng; giữ nút web gửi MOVE mới, nhả gửi STOP nội bộ. Forward chỉ chạy khi
sensor **mới, hợp lệ và hướng giữa**. <15cm dừng/bật còi; dữ liệu lỗi/timeout/stale dừng.
Khi an toàn trở lại, không chạy lại cùng sequence đã bị chặn; chỉ nhận lệnh mới còn TTL.
Lùi/quay dùng opt-in/burst giới hạn ở trên; sensor lỗi vẫn dừng mọi hướng.

Auto là state machine không delay dài: DRIVE → LOOK LEFT → LOOK RIGHT → CENTER → TURN
→ WAIT NEW FRONT → DRIVE/HALT. >=40cm duty thường, 15–<40cm duty chậm/beep100ms,
<15cm dừng và quét hai phía. Chọn phía xa hơn nếu ít nhất40cm, turn tối đa400ms; yêu cầu
mẫu trước mặt **sau khi quay dừng** trước đi tiếp. Không có đường thì HALT; phải đổi mode/
nhận quyền lại để thử lại. Không kế thừa bước lùi400ms hoặc tự lùi khi khoảng cách không
đổi3s của code cũ: cảm biến trước không chứng minh đường sau an toàn. Giữ settle600ms,
góc servo và turn400ms từ code mẫu.

Sensor task dùng GPIO edge ISR + task notification, trigger10µs, echo timeout tối đa30ms,
nhận pulse <=25ms và khoảng2–400cm. No echo/out-of-range là SENSOR_ERROR/null, không phải
999cm đường trống. Cùng một cảm biến khi quét sẽ đo hướng đang quay; lúc servo chưa ổn
định không công bố khoảng cách hợp lệ (SENSOR_ERROR/null tạm thời), motor vẫn dừng.
Không suy ra lỗi cảm biến chỉ vì khoảng cách đứng yên.

Control tick10ms, watchdog20ms ở core1; HTTP ở core0. Mọi cập nhật motor/servo/relay được
đồng bộ qua mutex duy nhất, không giữ mutex trong HTTP/chờ echo. Watchdog không phụ thuộc
HTTP: TTL, hạn lease/authorization, heartbeat, poll freshness1s, lỗi sensor/driver đều
chặn actuation. Task watchdog ESP-IDF panic/reset5s là lớp bổ sung nếu task bị treo.
Đây là các **chu kỳ mục tiêu phần mềm**, chưa đo thời gian dừng trên xe thật.

Deadline dùng monotonic: hạn từ server trừ toàn bộ RTT và margin20ms, cap theo TTL config;
duplicate không kéo dài hạn hoặc chạy lại. STOP/mode/generation đổi dừng trước thay intent.
Auto chỉ chạy sau safe APPLIED receipt và KEEPALIVE còn hạn. Permit hết hạn, Wi-Fi lỗi,
session lỗi hoặc Auto fail-safe bắt buộc boot UUID/session mới, không resume Auto cache.
Firmware có thể chọn reset session thay vì retry lệnh chuyển động sau kết quả mạng không
chắc chắn; authenticate retry giữ cùng boot UUID để không đăng ký boot mới liên tục.

ACK RECEIVED rồi APPLIED/REJECTED/FAILED, APPLIED không xác nhận xe đã di chuyển. Mode ACK
có STOPPED/mode/safe_mode_switch tường minh; motor giữ dừng đến ACK thành công. Telemetry
từ sensor và output driver, không tạo số đo giả. Không có encoder nên actual_movement là
trạng thái điều khiển điện của driver, không đo vận tốc/bánh xe trượt. ACK thành công mới
đưa command_sequence_applied vào telemetry. Sample/heartbeat counters theo boot, telemetry
429 giữ body/counter để retry, generation đổi bỏ sample đang chờ. Không log response body.

## Module và kiểm thử trên host

`src/`: config; motor/servo/outputs/sensor; robot mutex/state; manual/auto/safety;
wifi/http; protocol/device/telemetry; console; main chỉ khởi tạo tasks.

```bash
# Từ gốc repository, sau pio run để tải managed cJSON
mkdir -p firmware/.pio/host
cc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -g \
  -I firmware/src -I firmware/managed_components/espressif__cjson/cJSON \
  firmware/src/protocol.c firmware/src/telemetry.c \
  firmware/managed_components/espressif__cjson/cJSON/cJSON.c \
  firmware/test/protocol_test.c -lm -o firmware/.pio/host/protocol_test
ASAN_OPTIONS=detect_leaks=0 firmware/.pio/host/protocol_test
ASAN_OPTIONS=detect_leaks=0 backend/.venv/bin/python firmware/tools/check_contract.py
python3 -m unittest discover -s firmware/test -p 'test_*.py' -v
python3 firmware/tools/check_board.py
```

Đây là kiểm thử codec/time/deadline và cấu hình, không giả lập GPIO/ESP32. Không thay thế
thử nghiệm xe thật. Chi tiết kết quả và quy trình thử từng hướng/sensor/mất mạng:
[phase-6b-report.md](../docs/phase-6b-report.md).
