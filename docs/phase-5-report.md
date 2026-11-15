# Phase 5 — Robot Control & Realtime

Triển khai ngày 15/11/2026 trên codebase Phase 4. Đã đọc README/báo cáo Phase 4, kiểm tra
Auth/JWT/RBAC, Robot/ControlSession models, migrations, API đọc/quản trị robot, routes,
API client, Query scope và các tests hiện có. Giữ authentication, Admin management,
Dashboard và database sessions; không khởi tạo lại project/môi trường.

## Chức năng hoàn thành

- Lease acquire/renew/release/session gắn đúng user và auth family, token chỉ lưu hash.
- PostgreSQL row locks và partial unique index bảo đảm một lease chưa đóng/robot; xử lý
  lease cũ trước acquire mới. Có test tranh lease và Move/Stop đồng thời bằng DB connections riêng.
- Kiểm tra active/Online, TTL, owner, JWT/session hiện hành ở backend; Admin không bypass lease.
- Thu hồi khi logout/revoke auth, disable user/robot, rotate credential, timeout, Offline
  hoặc WebSocket của phiên sở hữu bị đóng. Sweeper chạy theo lifespan, không phụ thuộc browser.
- Command state/history trong PostgreSQL, sequence tăng theo robot, generation fencing,
  request idempotency và client high-water sequence chống replay/thứ tự cũ. Có giới hạn lưu trữ.
- Manual MOVE bốn hướng, STOP nội bộ, Manual/Auto switching; chỉ mở Manual sau ack an toàn.
  Requested mode tách actual mode, backend ACCEPTED tách xác nhận RECEIVED/EXECUTED của thiết bị.
- Auto permit TTL ngắn được làm mới khi renew; hết hạn hoặc mất lease vô hiệu hóa tự hành cũ.
- WebSocket xác thực bằng frame đầu, kiểm tra Origin và quyền robot, không có token URL;
  snapshot/ping đọc PostgreSQL định kỳ hỗ trợ nhiều workers, không dùng global command state.
- Internal device adapter có command envelope/ack/telemetry để Phase 6 tái sử dụng credential
  service; chưa public Device HTTP API, không giả lập động cơ hoặc heartbeat production.
- Schema CLEAR/BLOCKED/SENSOR_ERROR, distance hữu hạn, actual motion và Buzzer nullable;
  dữ liệu chưa có/stale được hiển thị rõ, backend không tính ngưỡng điều khiển từ khoảng cách.
- `/robots/:id` trở thành RobotControlPage: Nhận/Thoát điều khiển, Manual/Auto, D-Pad đúng
  bốn nút Tiến/Lùi/Quay trái/Quay phải, thông tin actual state/kết nối/cảm biến.
- Chuột/touch/keyboard WASD/Arrow Keys; giữ gửi tuần tự tối đa khoảng 4 Hz; nhả/cancel STOP.
  Blur, hidden tab, mất WS, lỗi move, hết lease, logout và unmount ngừng refresh, cố STOP/release.
  Đã xử lý response acquire đến muộn sau unmount/mất focus để không giữ lease ngoài ý muốn.
- WS reconnect backoff, heartbeat watchdog phía UI, single subscription theo trang, cleanup
  timers/socket và REST fallback; điều khiển chỉ mở khi WS đã nhận snapshot hợp lệ.

Không tạo Stop/Emergency Stop button hoặc Emergency Stop API. Không sửa firmware, GPIO,
driver cảm biến/servo/còi, không thêm simulator, MQTT hoặc Device Communication HTTP API.

## API

Prefix `/api/v1/robots/{robot_id}/control`, Bearer access JWT bắt buộc:

| Endpoint | Response thành công |
| --- | --- |
| POST `/acquire` | 201, lease + secret trả một lần + renew_after_ms |
| POST `/renew` | 200, lease expiry mới |
| POST `/release` | 204 |
| GET `/session` | 200, lease view theo phiên |
| GET `/state` | 200, trạng thái yêu cầu và actual state |
| POST `/mode` | 202, MODE command |
| POST `/move` | 202, MOVE command bốn hướng |
| POST `/stop` | 202, STOP command nội bộ |

Renew/release dùng control_session_id + lease_token; action thêm request_id UUID và
client_sequence tăng theo lease. Không trả lease secret trong state/events hoặc command
cho người xem khác. HTTP 202 không có nghĩa động cơ đã thực hiện.

WS `/api/v1/ws/robots/{robot_id}` gửi `robot.state` khi thay đổi và `ping` khi không đổi.
Frame đầu `authenticate` mang JWT memory, timeout 5 giây, không chấp nhận query string.
Backend kiểm tra lại JWT/user/auth family/robot mỗi lần snapshot. Snapshot được lấy từ
DB theo interval mặc định 1 giây, không phải push tức thì từ thiết bị. Auth fail 4001,
không được truy cập robot 4003, policy 1008, DB error 1011.

Chi tiết schema, mode ack, permit/watchdog và chuẩn bị Phase 6:
[robot-control-protocol.md](robot-control-protocol.md).

## Database và cấu hình

Migration **0003_control** kế thừa **0002_auth**, không sửa migration cũ:

- `robot_control_states`: sequence/generation, requested/actual mode, pending/confirmed fence,
  actual movement/obstacle/distance/buzzer/report timestamps.
- `robot_commands`: UUID, robot/lease FK, seq/gen, request hash/id, client sequence, kind,
  mode/direction, TTL/status; unique robot+sequence và robot+request_id, expiry/history indexes.
- `control_sessions`: auth_session_id FK/index, last_client_sequence >=0. Giữ unique index
  một open lease/robot của Phase 1.
- Trigger đóng lease khi auth family revoke; trigger vô hiệu hóa commands/generation khi
  lease ended_at được đặt. Logout/Admin paths hiện có nhận cơ chế này trong cùng transaction.

Đã chạy upgrade trên PostgreSQL hiện có, head 0003_control; check không có schema drift.
Không reset database, xóa volume hoặc seed heartbeat/user/robot giả vào development.
Integration tests dùng smartrobot_test/schema UUID riêng; downgrade chỉ trong schema test.

Biến `.env.example` bổ sung:

| Biến | Mặc định |
| --- | --- |
| CONTROL_LEASE_SECONDS | 10 |
| MANUAL_COMMAND_TTL_MS | 700 |
| MODE_COMMAND_TTL_MS | 3000 |
| COMMAND_HISTORY_LIMIT | 1000/robot |
| COMMAND_RETENTION_DAYS | 7 |
| CONTROL_CLEANUP_INTERVAL_SECONDS | 1 |
| WEBSOCKET_INTERVAL_SECONDS | 1 (giới hạn 0.1–2) |

UI renew theo giá trị backend, mặc định 1500 ms; Auto permit/handshake TTL mặc định 3 giây.
Manual refresh 250 ms sau khi response hoàn tất, control POST timeout 900 ms. WS client
watchdog 4 giây, backoff 0.5–5 giây. Thay cấu hình cần giữ đủ khoảng cho latency mạng và
watchdog thiết bị; TTL hết phải dừng thay vì tiếp tục chuyển động từ cache.

## Kết quả kiểm thử thực tế

| Kiểm tra | Kết quả |
| --- | --- |
| Toàn bộ `uv run --locked pytest -q` | **203 passed**, 68.19 giây |
| Ruff check | Pass |
| Ruff format --check | Pass, 75 Python files |
| Alembic upgrade head | Pass, 0002_auth → 0003_control |
| Alembic current | 0003_control (head) |
| Alembic check | No new upgrade operations detected |
| `npm test` | **101 passed**, 10 files, 4.00 giây |
| `npm run lint` | Pass |
| `npm run typecheck` | Pass |
| `npm run build` | Pass, bundle tạo thành công |
| Uvicorn/httpx/WebSocket TCP thật | Pass: acquire/MOVE/STOP/release và state event |
| Visual/responsive browser thật | Chưa kiểm chứng — browser host unavailable |

Giữ toàn bộ tests Phase 1–4. Backend mới kiểm tra acquire/renew/release, hết lease/Offline,
JWT/owner/secret, hai user tranh lease, bốn hướng, safe Manual ack, Auto chuyển lại Manual,
Auto keepalive TTL, Stop/Mode fencing, Move/Stop race, idempotency/replay, history limit,
logout/disable lifecycle, stale ack/device credential sai, obstacle/sensor errors, idle
telemetry không ack mode, WS auth/Origin/robot authorization/reconnect/disconnect/revocation.
Có hồi quy Manual đã xác nhận giữ lease khi MODE cũ hết TTL trong lúc đứng yên.

`test_http_control.py` mở Uvicorn TCP port tạm với database test; HTTP acquire201, MOVE202,
STOP202 có sequence tăng, release204; WebSocket authenticate frame đầu và nhận state event.
Actual Manual được xác nhận qua adapter chỉ trong test fixture; không mở Device API giả.
Server được dừng sau test. Các kiểm tra denial/auth WS dùng TestClient riêng.

Frontend giữ tests auth/Admin/Dashboard/polling cũ, cập nhật mock control state và assertion
detail mới thay placeholder. Tests mới dùng jsdom/fake timers, fetch và WebSocket mocks:
D-Pad bốn hướng, mouse/touch/keyboard, cancel/blur/hidden/unmount, queue order, held refresh,
acquire/release/expiry, Offline/Busy, mode pending, accepted khác actual, lỗi mạng, obstacle,
sensor error, WS backoff/watchdog/denial/cleanup, logout gửi release trước revoke và response
acquire tới sau unmount, request treo không chặn STOP vô hạn. Không dùng dữ liệu mock trong source production.

## File thay đổi

Đã sửa:

```text
.env.example
README.md
backend/app/core/config.py
backend/app/api/dependencies.py
backend/app/api/router.py
backend/app/main.py
backend/app/models/__init__.py
backend/app/models/control_session.py
backend/tests/test_auth.py
backend/tests/test_database.py
frontend/vite.config.ts
frontend/src/services/api.ts
frontend/src/routes/AppRoutes.tsx
frontend/src/pages/RobotDetailPage.tsx
frontend/src/test/api.test.ts
frontend/src/test/UserDashboard.test.tsx
```

Đã thêm:

```text
backend/app/models/control.py
backend/app/schemas/control.py
backend/app/repositories/control.py
backend/app/services/control.py
backend/app/services/device_control.py
backend/app/services/control_cleanup.py
backend/app/api/routes/control.py
backend/app/websocket/__init__.py
backend/app/websocket/robots.py
backend/migrations/versions/0003_control_robot_control_and_command_lifecycle.py
backend/tests/test_control.py
backend/tests/test_http_control.py
frontend/src/types/control.ts
frontend/src/services/robotControlService.ts
frontend/src/services/robotWebSocket.ts
frontend/src/hooks/useRobotControl.ts
frontend/src/components/control/ControlLeaseManager.tsx
frontend/src/components/control/ControlModeSelector.tsx
frontend/src/components/control/ManualDPad.tsx
frontend/src/components/control/ObstacleStatus.tsx
frontend/src/pages/RobotControlPage.tsx
frontend/src/test/controlFixtures.ts
frontend/src/test/ControlLifecycle.test.tsx
frontend/src/test/ManualDPad.test.tsx
frontend/src/test/RobotControlService.test.ts
frontend/src/test/RobotControlPage.test.tsx
frontend/src/test/RobotWebSocket.test.ts
docs/phase-5-report.md
docs/robot-control-protocol.md
```

RobotDetailPage giữ export tương thích và trỏ sang RobotControlPage; không còn placeholder
điều khiển cũ. Không thêm dependencies, đổi lockfiles hoặc xóa file. Repository chưa có
commit nền, danh sách này ghi thay đổi Phase 5, không coi mọi file untracked là file mới.

## Hướng dẫn nghiệm thu

```bash
# Terminal 1, từ backend
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers

# Terminal 2, từ frontend
npm run dev
```

1. Đăng nhập `http://127.0.0.1:5173/login`, mở Dashboard và Xem xe.
2. Xe mới/không có heartbeat phải Offline; bốn nút điều khiển và Nhận điều khiển bị khóa.
   Xác nhận không có nút Stop/Emergency Stop, vẫn xem tên/Device ID/heartbeat UTC.
3. Mở DevTools Network → WS: một subscription của trang, frame đầu authenticate; không
   có JWT/lease secret trong URL. State/ping định kỳ; disable robot từ Admin dẫn tới 404.
4. Thử mobile/tablet/desktop, Tab navigation và lỗi mạng. Các bước visual này cần nghiệm thu
   bằng browser thật vì agent không có browser host hoạt động.
5. Luồng Online/lease/ack/Manual/Auto hiện được kiểm tra qua test database, không chỉnh
   last_seen_at development hoặc dựng thiết bị giả để ép UI Online. Chạy:
   `uv run pytest -q tests/test_control.py tests/test_http_control.py` từ backend và
   `npm test` từ frontend để kiểm tra phần chưa có thiết bị.
6. Sau Phase 6 có Device API/ESP32, cần kiểm tra trực tiếp nhấn giữ/nhả, safe ack Manual,
   Auto handoff, cảm biến, Buzzer, watchdog và độ trễ dừng trên thiết bị thật.

## Lỗi đã sửa và giới hạn

- Đã sửa target keyboard là Window không có closest; kiểm tra Element trước xử lý input.
- Đã sửa TypeScript parameter properties không tương thích erasableSyntaxOnly, nullable
  expiry và React lint về state cập nhật trong effect; lint/typecheck/build cuối đã chạy.
- Bổ sung cleanup response acquire đến muộn và test local lease timeout độc lập WS.
- Control POST có deadline riêng ngoài AbortSignal, để refresh/fetch treo không khóa hàng
  đợi STOP vô hạn. Test hồi quy chờ move thực sự bắt đầu trước khi xếp STOP vào hàng đợi.
- Đã sửa expiry MODE Manual đã xác nhận để không đóng lease đang được renew khi đứng yên.
- **Chưa kiểm thử visual/responsive bằng browser thật**: inventory trả
  `The browser access host is unavailable`. Không có screenshot xác nhận UI.
- **Chưa kiểm chứng động cơ, thời gian dừng, watchdog cục bộ, HC-SR04, servo, Buzzer hoặc
  tránh vật cản Auto trên ESP32**. Hành vi này là hợp đồng giao thức; chưa có firmware/Device
  HTTP API gửi heartbeat/ack thực tế. UI không thông báo lệnh đã thực thi khi chỉ có 202.
- Snapshot WS có độ trễ theo interval; chưa có load test nhiều robot/clients, hardware-in-loop
  hoặc kiểm thử reverse proxy production. Cần cấu hình WebSocket Upgrade và HTTPS/WSS khi deploy.
- Khi mạng/DB lỗi, backend/frontend không thể chứng minh động cơ dừng; firmware bắt buộc
  kiểm tra TTL/lease/generation và watchdog mà không phụ thuộc frontend hay WS.

Dừng ở Phase 5 để nghiệm thu; không tự động triển khai Phase 6.
