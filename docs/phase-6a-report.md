# Phase 6A — Real ESP32 Device Communication

Triển khai ngày 15/11/2026 trên source Phase 5. Đã đọc README, phase-5-report và
robot-control-protocol; kiểm tra Auth/RBAC, models/migrations, credential rotation,
Control Lease/TTL/sequence/idempotency, WebSocket và RobotControlPage/Query/API client.
Tái sử dụng ControlService, credential service, PostgreSQL session/locking và WS snapshot.
Không khởi tạo lại project hoặc thay hệ thống authentication hiện có.

## Hoàn thành

- Device HTTP API v1 độc lập User JWT; credential trong headers, hash-only trong DB.
  Robot disabled và secret cũ sau rotate bị từ chối. Không nhận query parameters.
- HTTPS mặc định; production không cho opt-in HTTP. HTTP development phải bật rõ ràng,
  chỉ nhận IP private/loopback; vẫn yêu cầu firewall LAN và không public Internet.
- Device session theo boot UUID, auth idempotency, tombstone boot cũ chống request đến muộn.
  Boot mới hủy lease/lệnh cũ, tăng generation, xóa cached actual state và không tự Online.
- Heartbeat counter tăng theo boot, last_seen_at dùng giờ PostgreSQL UTC. Duplicate giữ
  timestamp cũ, không thể replay heartbeat để kéo dài Online. Heartbeat sau Offline thu
  hồi lease cũ trước cập nhật Online. Interval/timeout qua environment/config response.
- Poll current command có sequence/generation/lease, thời hạn authorization và desired
  mode rõ ràng. Chỉ trả command hiện hành, còn TTL và thuộc lease còn quyền. Không trả
  STOP cũ của lease đã đóng. Null/false authorization bắt buộc firmware dừng/hủy Auto.
- Poll lặp không thay ACK, không kéo dài TTL. Giữ idempotency, row locks và sequence của
  Phase 5; không tạo queue thực thi lại chuyển động cũ.
- ACK RECEIVED/APPLIED/REJECTED/FAILED có timestamp/hash. Kiểm tra ID, robot, seq/gen,
  TTL/lease; terminal/backwards/conflicting ACK bị từ chối. Duplicate trả receipt cũ mà
  không cập nhật state hoặc làm lease/lệnh cũ sống lại. FAILED/REJECTED thu hồi lease.
- APPLIED chỉ là firmware chấp nhận áp dụng; không gán actual movement từ ACK thông
  thường. Safe mode handoff bắt buộc APPLIED + đúng mode + STOPPED + safe_mode_switch.
  Chưa handoff thì Manual bị khóa; ACK/telemetry cũ không mở khóa mode mới.
- Telemetry lưu PostgreSQL: robot/session/sample sequence, generation, optional applied
  sequence, distance nullable, obstacle, mode/movement và Buzzer nullable. Timestamp do
  server nhận mẫu gán, không tin client timestamp để cập nhật freshness.
- Sample high-water và generation chặn packet cũ; duplicate không ghi thêm/đổi timestamp.
  Rate limit mặc định 5 Hz, Retry-After; history mặc định 10000 mẫu/robot và 7 ngày, dọn batch.
- WebSocket `robot.state` hiện có phản ánh heartbeat, actual telemetry và ACK mới. Nguồn
  trạng thái vẫn PostgreSQL, snapshot mặc định 1 giây, hoạt động qua nhiều workers.
- Frontend thêm Requested Mode và xác nhận thiết bị riêng với backend acceptance và
  actual movement. Unknown/stale/disconnected không hiển thị cached sensor/ACK như live.
  D-Pad đúng bốn hướng và các safety/lease behaviors Phase 5 được giữ nguyên.
- Hợp đồng ESP-IDF đủ request/response, retry/error/reboot/ordering/watchdog, flowchart và curl.

**Không xây dựng Robot Simulator**. Không có service/chương trình giả lập ESP32, firmware,
PlatformIO setup, GPIO, driver HC-SR04/servo/motor/Buzzer hoặc MQTT. TestClient/HTTP requests
tự động chỉ phục vụ kiểm thử trên DB test, không phải simulator. Cột is_simulated đã có từ
Phase 1 được giữ nguyên, không phát triển chức năng giả lập.

## APIs và dữ liệu giao tiếp

Prefix `/api/v1/devices`, JSON; mọi request gửi X-Device-ID và X-Device-Secret. Bốn API sau
authenticate còn cần X-Device-Session. Không dùng User JWT/cookie; không gửi credential URL.

| Method/path | Dữ liệu chính | Response |
| --- | --- | --- |
| POST `/authenticate` | boot_id UUID, firmware_version? | 200 robot/session, seq/gen, server_time, timing config |
| POST `/heartbeat` | heartbeat_sequence | 200 last_seen_at, seq/gen, duplicate |
| GET `/commands/current` | Không body/query | 200 command/null, desired mode, authorization/lease expiry |
| POST `/commands/ack` | command_id, seq/gen, status, safe handoff nếu cần | 200 ACK timestamp/duplicate |
| POST `/telemetry` | robot_id, sample/seq/gen, actual fields, applied sequence? | 200 recorded_at/duplicate |

Movement telemetry dùng STOPPED/FORWARD/BACKWARD/TURN_LEFT/TURN_RIGHT; command direction
dùng STOP thay STOPPED. ControlState WS giữ STOP tương thích frontend Phase 5, DB enum
telemetry cũ giữ STOP/LEFT/RIGHT nội bộ. API có mapping tường minh, firmware chỉ dùng schema
Device API. Obstacle CLEAR/BLOCKED/SENSOR_ERROR; không có backend thuật toán tránh vật cản.

Lỗi chính: 400 query policy; 401 credential/activation; 403 transport policy/sai robot;
409 session/fence/ACK/sequence xung đột; 422 validation đã redact input; 429 telemetry rate;
5xx/network xử lý fail-safe tại firmware. GET không ACK, heartbeat không gia hạn command.

Schema JSON đầy đủ và flowchart: [esp32-device-api.md](esp32-device-api.md).
Lease/control/WS chung: [robot-control-protocol.md](robot-control-protocol.md).

## Database và migration

Migration mới **0004_devices**, parent **0003_control**; không sửa migrations đã áp dụng.

- Bảng device_sessions: UUID, robot FK, boot UUID unique theo robot, một open session/robot,
  firmware version, start/end, heartbeat/sample counters, timestamps và sample fingerprint.
- RobotCommand thêm acknowledgement, acknowledged_at, acknowledgement_hash, constraint
  status APPLIED/FAILED và ACK allowlist, index robot+acknowledged_at.
- RobotTelemetry thêm device_session FK, sample sequence unique/session, generation,
  applied sequence, obstacle/Buzzer và checks. Giữ schema mode/movement/timestamp cũ để
  không phá dữ liệu hoặc tests Phase 1–5.
- Cập nhật lifecycle trigger trong migration mới để APPLIED cũng bị supersede khi đóng
  lease. Downgrade khôi phục semantics/status cũ; downgrade chỉ được kiểm tra trong DB test.
- Credential rotate/disable/đổi Device ID đóng device sessions trong cùng transaction
  với heartbeat/lease invalidation và audit hiện có.
- Telemetry history prune tối đa 1000 mẫu/lần, age cleanup qua lifespan sweeper; backlog
  lịch sử lớn được dọn dần. Tombstone boot/counters không bị xóa khi prune telemetry.

Đã chạy upgrade trên PostgreSQL development đang có, head 0004_devices; Alembic check
không có schema drift. Không reset DB, xóa Docker volume, thay secrets .env hoặc seed
heartbeat/telemetry giả vào development. Các tests dùng DB test/schema UUID cô lập.

Biến mới trong `.env.example`:

```text
DEVICE_ALLOW_INSECURE_HTTP=false
DEVICE_HEARTBEAT_INTERVAL_MS=2000
DEVICE_POLL_INTERVAL_MS=100
DEVICE_TELEMETRY_MIN_INTERVAL_MS=200
TELEMETRY_RETENTION_DAYS=7
TELEMETRY_HISTORY_LIMIT=10000
```

ROBOT_OFFLINE_AFTER_SECONDS=15 và command TTL/lease configs Phase 5 được tái sử dụng.
Heartbeat response clamp interval không quá timeout/3, giữ tương thích timeout ngắn của
Phase 4. Không thêm dependencies hoặc sửa lockfiles.

## Kết quả kiểm thử thực tế

| Kiểm tra | Kết quả |
| --- | --- |
| Toàn bộ `uv run --locked pytest -q` | **250 passed**, 98.55 giây |
| Ruff check | Pass |
| Ruff format --check | Pass, 85 Python files |
| Alembic upgrade head | Pass, 0003_control → 0004_devices |
| Alembic current | 0004_devices (head) |
| Alembic check | No new upgrade operations detected |
| Frontend tests | **108 passed**, 11 test files, 4.65 giây |
| Frontend lint | Pass |
| TypeScript check | Pass |
| Frontend build | Pass |
| Uvicorn HTTP Device API và WebSocket TCP thật | Pass qua automated integration test |
| Visual/responsive browser | Chưa kiểm chứng, browser host unavailable |
| ESP32/TLS client/phần cứng thật | Chưa kiểm chứng, thuộc Phase 6B |

Giữ toàn bộ 203 backend/101 frontend tests Phase 1–5, thêm 47 backend và 7 frontend cases.
Database expected head/table assertions cập nhật cho migration mới; không bỏ test cũ.

Backend kiểm tra auth thiếu/sai/User JWT/disabled/revoked secret, mọi Device route được
bảo vệ, auth retry không Online, heartbeat replay/timeout, fetch duplicate không ACK,
safe mode handoff, APPLIED không suy diễn movement, terminal ACK/idempotency, stale ACK,
TTL, release/logout/lease timeout/Auto timeout/Offline, reboot/old boot và session invalidation,
sensor validation/CLEAR/BLOCKED/SENSOR_ERROR, persistence, rate limit, conflicting replay,
retention, multi-robot isolation và transport LAN/production policy.

Race tests: giữ concurrent acquire/Move-vs-Stop Phase 5; thêm ACK-vs-Stop trên PostgreSQL
connections/thread riêng, final command vẫn STOP hoặc old ACK bị 409. Thêm public Auto→
Manual handshake và duplicate Auto ACK không xác nhận mode Manual mới; old generation
telemetry không ghi đè sau Stop, heartbeat sau Offline thu hồi lease trước Online.

`test_http_devices.py` mở Uvicorn port TCP tạm trên loopback: authenticate, heartbeat,
unauth401, acquire, fetch MODE, safe APPLIED, MOVE, fetch/ACK, POST BLOCKED/STOPPED telemetry,
duplicate telemetry rồi nhận WS robot.state có distance/Buzzer/APPLIED. Tắt access logs,
dùng DB test, không public endpoint test hoặc mock Device API trong production. Server
tự dừng cuối test. Đây là HTTP thật, không kiểm chứng ESP32/TLS/motor thật.

Frontend tests thêm bốn ACK statuses, old APPLIED không xác nhận command mới, unknown/stale
sensor handling và WS frame APPLIED vẫn actual STOP, mất WS xóa live claims. Giữ D-Pad,
pointer/touch/WASD/Arrow Keys, logout/lease/polling/auth/Admin tests. Mocks chỉ ở thư mục test.

## Files thay đổi

Đã sửa:

```text
.env.example
README.md
docs/robot-control-protocol.md
backend/app/api/router.py
backend/app/core/config.py
backend/app/models/__init__.py
backend/app/models/control.py
backend/app/models/robot_telemetry.py
backend/app/repositories/control.py
backend/app/schemas/control.py
backend/app/services/admin_robots.py
backend/app/services/control.py
backend/app/services/control_cleanup.py
backend/app/services/device_control.py
backend/app/services/device_credentials.py
backend/tests/test_database.py
frontend/src/hooks/useRobotControl.ts
frontend/src/pages/RobotControlPage.tsx
frontend/src/types/control.ts
frontend/src/test/RobotControlPage.test.tsx
```

Đã thêm:

```text
backend/app/api/device_dependencies.py
backend/app/api/routes/devices.py
backend/app/models/device.py
backend/app/repositories/devices.py
backend/app/schemas/devices.py
backend/app/services/devices.py
backend/migrations/versions/0004_devices_device_communication.py
backend/tests/test_device_contract.py
backend/tests/test_devices.py
backend/tests/test_http_devices.py
frontend/src/components/control/CommandAcknowledgement.tsx
frontend/src/test/DeviceTelemetry.test.tsx
docs/esp32-device-api.md
docs/phase-6a-report.md
```

device_control.py/device_credentials.py sửa docstrings compatibility/caller-lock cho đúng
Phase 6A; không thay authentication hash hoặc credential format Phase 3. Repository chưa
có commit nền; danh sách này ghi nhận Phase 6A, không coi mọi file untracked là file mới.
Không xóa file, đổi firmware, project PlatformIO hoặc Docker configuration.

## Hướng dẫn nghiệm thu và cấu hình ESP32

1. Backend: `uv run alembic upgrade head`; chạy Uvicorn. Web: `npm run dev` như README.
2. Admin thêm robot thật hoặc rotate credential, giữ secret một lần ở cấu hình thiết bị
   được bảo vệ. Không sửa backend source để đổi credential. Robot chưa heartbeat phải Offline.
3. Chuẩn bị HTTPS server/CA/hostname. Chỉ LAN phát triển mới opt-in HTTP và bind 0.0.0.0,
   `--no-proxy-headers --no-access-log`; giới hạn firewall, không port-forward.
4. ESP32 Phase 6B cấu hình Wi-Fi SSID/password, laptop base URL/port, CA/hostname, Device
   ID/secret, boot UUID, RAM counters/session/fences, timers/HTTP timeout/retry và watchdog.
   Không dùng localhost trên ESP32. Đọc toàn bộ Device API trước viết firmware.
5. Không có ESP32 vẫn chạy được `uv run pytest -q tests/test_devices.py tests/test_http_devices.py`
   và frontend tests. Curl examples ở Device API dùng header file tạm 0600, không log secret.
6. Khi thiết bị thật heartbeat, Dashboard/Control Page hiện Online. Acquire → MODE Manual
   → safe ACK mới mở D-Pad. Nhấn/nhả vẫn internal Stop. Theo dõi ACK riêng với actual
   telemetry; không kết luận motor chạy từ APPLIED.
7. Phase 6B cần đo trực tiếp mất Wi-Fi, timeout server, reboot, rotate/disable/logout,
   Auto authorization hết hạn, sensor fail-safe và thời gian dừng vật lý.

## Lỗi và phần chưa kiểm chứng

- Các lỗi Ruff import/format/line length trong lúc viết đã sửa, checks cuối pass.
- Bổ sung guard MODE APPLIED thiếu safe handoff để không nhận ACK terminal khiến mode
  pending không thể được xác nhận tiếp; test fail-fast409 rồi proper handoff đạt.
- Safe ACK không tái sử dụng sensor cached như telemetry mới; frontend mất WS không giữ
  cached sensor/ACK là live. APPLIED vẫn không suy diễn actual movement.
- Không còn lỗi kiểm thử được ghi nhận. **Chưa kiểm chứng firmware, ESP32 Wi-Fi/TLS client,
  GPIO/motor/HC-SR04/servo/Buzzer, thuật toán Auto hoặc độ trễ dừng vật lý**. Watchdog local
  là yêu cầu giao thức, backend không thể thay nó khi mạng/nguồn thiết bị mất.
- Browser inventory trả `The browser access host is unavailable`; chưa kiểm thử visual/
  responsive trên browser thật. Tests React dùng jsdom, không thay thế nghiệm thu visual.
- Chưa load test nhiều ESP32/clients, TLS reverse proxy production hoặc mạng LAN thật.
  WS là DB snapshot mỗi giây, không phải push tức thì. Telemetry retention chạy batch;
  tombstone boot history vẫn giữ để chống replay, chưa có archival riêng cho bảng này.

Dừng tại Phase 6A để nghiệm thu. Không tự triển khai Phase 6B hoặc Robot Simulator.
