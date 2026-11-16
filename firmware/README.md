# SmartRobot ESP32 — ESP-IDF / PlatformIO

Firmware C native cho project PlatformIO hiện có: esp32dev, ESP32-D0WD-V3, ESP-IDF 6.1.0,
Flash 4MB, UART 115200. Không dùng Arduino, web server ESP32, MQTT hoặc Robot Simulator.
Giao thức giữ nguyên [Device API](../docs/esp32-device-api.md) của Phase 6A.

Bản **6b-15** hỗ trợ lượt mượn không hết hạn (`lease_expires_at=null`), giữ TTL hữu hạn
cho lệnh/Auto permit. Backend migration **0005_persistent_borrow** giữ người mượn qua
Offline, WebSocket ngắt, logout và thiết bị re-handshake; chỉ Trả xe hoặc thu hồi quản trị
mới đóng lượt mượn. Firmware 6b-2 không đọc được authorized envelope có lease expiry null:
nạp firmware mới trước khi bật backend sử dụng hạn null. 6b-5 vẫn đọc được hạn hữu hạn từ backend cũ.
Để giữ relay lúc idle cần backend mới có `control_session_id` ở cấp ngoài envelope.

Relay GPIO26 được người dùng xác nhận cấp nguồn motor. Từ **6b-5**, lượt mượn hợp lệ
bật và giữ relay active-low, kể cả Manual idle, STOP hoặc đổi mode. Relay chờ 50ms ổn
định trước PWM; trả xe/watchdog/lỗi nặng tắt nguồn. Auto giữ lựa chọn
khi khôi phục kết nối và cần handoff/permit mới. Xem [relay theo lượt mượn](../docs/fixes/borrow-powered-relay.md) và [retry/Auto 6b-4](../docs/fixes/motor-power-relay-and-auto-recovery.md).

Serial mới có `Poll OK` khi idle (mỗi 5 giây), `RX seq=... kind=...` khi nhận lệnh,
`ACK ... result=...` lúc handoff và log thay đổi output/duty. Gõ `status` để xem cấu hình
motors/blind/PWM, sequence đã thấy/đã ACK, deadline và cảm biến. Log không chứa secrets.
Thông tin PWM chỉ là tín hiệu điện, chưa đo bánh xe. Xem quy trình chẩn đoán và nghiệm thu:
[persistent-borrow-and-motion.md](../docs/fixes/persistent-borrow-and-motion.md).

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
Trái 0/PWM-phải/PWM-trái/0; Phải PWM-phải/0/0/PWM-trái; Dừng 0/0/0/0.
Người dùng xác nhận **OUT1/2 = bánh phải, OUT3/4 = bánh trái**. Bản **6b-8** đảo lại
chiều pivot của 6b-7 theo thử nghiệm thực tế người dùng báo; giữ nguyên tiến/lùi và trim.
[Auto lùi tìm đường và cân bánh](../docs/fixes/auto-backup-and-wheel-trim.md).
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
- `left_motor_percent` / `right_motor_percent`: bù PWM riêng, mặc định100/83.5 theo mức
  cân người dùng yêu cầu, khoảng50–150. Cân ở Manual đứng yên với `trim LEFT% RIGHT%`, lưu bằng
  `trim save`. Chưa có encoder, mức mặc định là điểm bắt đầu để cân trên xe thật.
  Hỗ trợ một chữ số thập phân, ví dụ `trim 100 83.5` hoặc `trim 100 83,5` trên Serial;
  NVS mới lưu phần mười phần trăm bằng u32 `left_pct10` / `right_pct10`.
- `auto_clearance_cm`: mặc định15 theo ver2_6, khoảng15–100cm, khoảng trống bên để cân nhắc rẽ.
- `auto_backup_ms`: mặc định400 theo ver2_6, khoảng50–400ms; lùi một lần sau khi chọn được hướng rẽ.
- `auto_turn_left_ms` / `auto_turn_right_ms`: mặc định400/400, khoảng100–1200ms.
- `http_timeout_ms`: giá trị NVS cũ vẫn đọc được; từ 6b-4 request có sàn timeout 400ms để
  hỗ trợ RTT 260ms trong log thực tế. Deadline lệnh/watchdog vẫn độc lập, không kéo dài TTL.
  Auth/TLS ban đầu timeout5s khi xe dừng.
- `relay_console`: giữ key tương thích NVS cũ; nguồn motor được điều khiển tự động.
  UART `relay off` hủy intent hiện tại; on/toggle bị từ chối để không bật nguồn ngoài luồng điều khiển.

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
  --port /dev/ttyUSB0 --baud 115200 write_flash 0x310000 secrets/robot_cfg.bin
pio device monitor --port /dev/ttyUSB0 --baud 115200
```

Tool esptool chạy qua môi trường PlatformIO để có pyserial. Nạp app thông thường không
ghi đè robot_cfg; cấp lại config chỉ ghi partition riêng. Nếu partition còn trắng hoặc
cấu hình sai, startup giữ motor/relay OFF và in lỗi chung, không in secret. Sau thay đổi
config cần reset. Không thử motor bằng upload command; điều khiển chỉ nhận từ backend lease.

Console: `status`, `trim LEFT% RIGHT%`, `trim save`, `relay off`. GPIO26 active-low là nguồn motor đã xác nhận trên xe này.
Lượt mượn được xác nhận bật nguồn. STOP/nhả hướng/Manual idle chỉ dừng PWM, giữ relay;
trả xe hoặc watchdog/lỗi nghiêm trọng tắt motor/relay. `relay off` cục bộ hủy intent hiện tại; các lệnh on/toggle thông báo
nguồn được quản lý tự động. Không thêm endpoint relay riêng.

6b-13 tự chuyển các bộ trim mặc định cũ85/100,90/100,105/100,100/85,100/80 hoặc100/82 thành100/83.5,
và bộ Auto30cm/300ms/400ms/400ms
thành15cm/400ms/400ms/400ms khi đọc NVS cũ. Cấu hình tùy chỉnh khác được giữ;
không ghi lại NVS khi khởi động. Sau khi chọn Manual và nhả hết nút, có thể dùng
`auto reference` để áp dụng bộ Auto ver2_6, `auto save` để lưu. `status` hiện thông số
đang dùng thực tế. Các lệnh save lưu revision để giá trị chủ động chọn được giữ qua reset.

## Điều khiển, Auto và watchdog

6b-10 đối chiếu `ver2_6_esp32.ino`: dùng ngưỡng15cm, lùi400ms, hãm100ms, quay400ms,
hãm100ms rồi đo lại. Giữ quét cả hai bên, chiều pivot6b-8 và chặn lặp lùi của6b-9.
[Chi tiết và nghiệm thu](../docs/fixes/auto-ver2_6-and-right-drift.md).
6b-11 bổ sung lùi một lần rồi quét lại khi chưa tìm được lối ở cả hai bên:
[nhánh phục hồi khi bị chắn](../docs/fixes/auto-backup-without-exit.md).
6b-12 chốt hướng trước lùi và chuyển ngay sang quay khi hết thời gian lùi;
ngưỡng chặn tiến không chặn bước lùi/quay:
[Auto lùi xong quay ngay](../docs/fixes/auto-immediate-turn.md).
6b-13 bỏ quay thoát gấp đôi thời gian; servo quét2°/20ms và giữ từng bên lấy đủ3 mẫu.
Hai bên kín thì lùi lâu hơn rồi đo lại, chỉ rẽ vào hướng đã đo đủ trống:
[quét chậm và rẽ theo dữ liệu](../docs/fixes/auto-slow-scan-side-turn.md).

Manual bốn hướng; giữ nút web gửi MOVE mới, nhả gửi STOP nội bộ. Forward chỉ chạy khi
sensor **mới, hợp lệ và hướng giữa**. <15cm dừng/bật còi; dữ liệu lỗi/timeout/stale dừng.
Khi an toàn trở lại, không chạy lại cùng sequence đã bị chặn; chỉ nhận lệnh mới còn TTL.
Lùi/quay Manual dùng opt-in/burst giới hạn ở trên; lỗi cảm biến trước vẫn dừng chuyển động.

Auto6b-14 chuyển logic `loop()`, `performRecoveryManeuver()` và `backUpAndTurn()`
của ver2_6 sang state machine phục vụ web. >=40cm tiến thường,15–<40cm tiến chậm,
<15cm quét trái trước. Trái>=15cm thì chọn trái, chỉ xét phải nếu trái bị chắn/chưa rõ.
Hai bên kín thì về giữa và kiểm tra lại, đúng bản mẫu, không còn nhánh lùi800ms/quay thoát.
Có hướng: về giữa lấy mẫu hợp lệ, lùi400ms → hãm100ms → quay400ms → hãm100ms → tiếp tục.
Khoảng cách đổi không quá5cm trong3 giây ở DRIVE kích hoạt lùi/quay trái như bản mẫu;
đây là heuristic khoảng cách, không phải đo kẹt bánh bằng encoder. Không còn giới hạn
một lượt lùi/đợt của các bản trước. Thông số lùi/quay tùy chỉnh vẫn đọc từ NVS.
Servo6b-15 đặt thẳng góc0°/90°/180° như Servo.write() của ver2_6, bỏ bước2°/20ms;
chờ ổn định600ms rồi đọc mẫu hợp lệ.
Chỉ chạy sau chọn Auto và handoff/permit hợp lệ. Đổi Manual/Trả xe/STOP/watchdog vẫn
ngắt được mọi bước, không chờ delay dài. No-echo vẫn là lỗi, không biến thành999cm trống.
Xem [Auto ver2_6 tích hợp web](../docs/fixes/auto-reference-web.md).

Sensor task dùng GPIO edge ISR + task notification, trigger10µs, echo timeout tối đa30ms,
nhận pulse <=25ms và khoảng2–400cm. No echo/out-of-range là SENSOR_ERROR/null, không phải
999cm đường trống. Cùng một cảm biến khi quét sẽ đo hướng đang quay; lúc servo chưa ổn
định không công bố khoảng cách hợp lệ (SENSOR_ERROR/null tạm thời), motor vẫn dừng.
Không suy ra lỗi cảm biến chỉ vì khoảng cách đứng yên.

Control tick10ms, watchdog20ms ở core1; HTTP ở core0. Mọi cập nhật motor/servo/relay được
đồng bộ qua mutex duy nhất, không giữ mutex trong HTTP/chờ echo. Watchdog không phụ thuộc
HTTP: TTL, hạn lease/authorization, heartbeat, độ mới giao lệnh/ACK mới 1s, lỗi sensor/driver đều
chặn actuation. Task watchdog ESP-IDF panic/reset5s là lớp bổ sung nếu task bị treo.
Đây là các **chu kỳ mục tiêu phần mềm**, chưa đo thời gian dừng trên xe thật.

Deadline dùng monotonic: hạn từ server trừ toàn bộ RTT và margin20ms, cap theo TTL config;
duplicate không kéo dài hạn hoặc chạy lại. STOP/mode/generation đổi dừng trước thay intent.
Auto chỉ chạy sau safe handoff được backend xác nhận và KEEPALIVE còn hạn. Permit hết hạn, Wi-Fi lỗi,
session lỗi hoặc Auto fail-safe bắt buộc boot UUID/session mới, không resume Auto cache.
HTTP timeout/408/429/5xx được retry trong cùng phiên, giữ deadline gốc. Telemetry retry
giữ nguyên body/counter và backoff 0.5–2s; ACK retry không apply lại command. Nếu MODE ACK
receipt bị mất nhưng GET mới giao MOVE/KEEPALIVE cùng lease/generation/mode đã xác nhận,
firmware có thể commit handoff gốc còn hạn trước nhận lệnh mới. Authenticate retry giữ boot UUID.

Firmware **6b-2** gửi trực tiếp ACK APPLIED/REJECTED/FAILED sau validation/apply để giảm
round-trip khi Manual refresh250ms; RECEIVED là tùy chọn của API, vẫn hỗ trợ trong codec.
APPLIED không xác nhận xe đã di chuyển. Mode ACK
có STOPPED/mode/safe_mode_switch tường minh; motor giữ dừng đến ACK thành công. Telemetry
từ sensor và output driver, không tạo số đo giả. Không có encoder nên actual_movement là
trạng thái điều khiển điện của driver, không đo vận tốc/bánh xe trượt. ACK thành công mới
đưa command_sequence_applied vào telemetry. ACK409 dừng output và poll lại ngay; telemetry409 chỉ bỏ mẫu cũ và poll lại,
không tự tạo boot mới chỉ vì command bị thay thế. Auto chỉ tiếp tục với command mới cùng
lease/generation, mode đã xác nhận, hạn cũ chưa hết và APPLIED receipt mới thành công;
watchdog/sensor vẫn hoạt động khi chờ. Command hết TTL trong đường truyền bị bỏ và dừng,
Manual không bị reset session chỉ vì gói cũ đến muộn. GET409/session lỗi,
sensor fault hoặc watchdog/Auto timeout thực vẫn re-handshake. Lỗi transport đơn lẻ không tạo boot mới. Sample/heartbeat counters theo boot, telemetry
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

Bản vá giữ quyền điều khiển khi ACK bị supersede, hướng dẫn cập nhật và kết quả kiểm thử:
[control-lease-ack-conflict.md](../docs/fixes/control-lease-ack-conflict.md).
