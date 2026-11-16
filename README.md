# SmartRobot

Nền tảng quản lý robot ESP32. Đã triển khai **Phase 1 — Backend Foundation** và
**Phase 2 — Authentication & Authorization**, **Phase 3 — User & Robot Management** và
**Phase 4 — User Dashboard & Robot Detail**, **Phase 5 — Robot Control & Realtime** và
**Phase 6A — Real ESP32 Device Communication**.
Admin có quản lý tài khoản/robot; USER có Dashboard, trang điều khiển, control lease và
WebSocket trạng thái và HTTP Device API cho nhiều ESP32 thật. Không có Robot Simulator.
Firmware ESP-IDF native Phase 6B đã triển khai đầy đủ module và build cho ESP32 Flash4MB;
chưa flash hoặc kiểm chứng xe thật. Xem [firmware README](firmware/README.md).

## Môi trường

- Python 3.12+, uv.
- Node.js/npm theo môi trường nvm hiện có.
- Docker Compose, PostgreSQL 18 theo `compose.yaml` hiện có.

Giữ nguyên `.env` và môi trường đang hoạt động. Với một bản checkout mới, sao chép
`.env.example` thành `.env`, tạo mật khẩu PostgreSQL và điền `DATABASE_URL` tương ứng.
Mật khẩu trong URL phải được URL-encode. Không commit `.env` hoặc `.env.test`.

```bash
docker compose up -d postgres
cd backend
uv sync --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Migration được chạy riêng qua Alembic; ứng dụng không tự tạo bảng khi khởi động.
Không xóa Docker volume để cập nhật schema.

## Health API

| Endpoint | Ý nghĩa |
| --- | --- |
| `GET /api/v1/health` | Liveness; trả `200 {"status":"ok"}`, độc lập với DB |
| `GET /api/v1/health/ready` | Kiểm tra kết nối DB bằng `SELECT 1`; trả 200 hoặc 503 |
| `GET /api/health` | Giữ tương thích endpoint ban đầu |
| `/docs` | OpenAPI/Swagger |

Readiness kiểm tra kết nối, không thay thế bước chạy và kiểm tra migration.
Endpoint health không trả connection string, SQL, thông tin người dùng hoặc robot.

## Authentication

`.env` cần có `JWT_SECRET` ngẫu nhiên ít nhất 32 bytes; xem `.env.example`.
Secret thực tế của môi trường hiện có đã được sinh và ghi vào `.env` cục bộ, không in ra logs.
Không có secret mặc định trong source. Nếu chưa có secret, development chỉ phục vụ health;
login trả 503. Production từ chối cấu hình thiếu secret, cookie không Secure hoặc origin không HTTPS.

Tạo Admin đầu tiên bằng terminal tương tác:

```bash
cd backend
uv run python -m scripts.create_admin
```

CLI yêu cầu username, email, mật khẩu và xác nhận mật khẩu. Password được nhập ẩn bằng
`getpass`, dài 12–128 ký tự. Không truyền password qua command line. Username gồm 3–64
ký tự chữ/số/`_.-`; email phải hợp lệ. CLI từ chối trùng username/email và từ chối tạo thêm
khi đã có Admin hoạt động. Chưa có tài khoản mặc định hoặc đăng ký công khai.

Khởi động frontend trong terminal khác:

```bash
cd frontend
npm ci
npm run dev
```

Mở `http://127.0.0.1:5173/login`, dùng tài khoản vừa tạo. Vite proxy `/api` tới
`http://127.0.0.1:8000`, giữ nguyên Origin. Frontend chỉ gọi đường dẫn cùng origin;
không cần đặt API URL hoặc secret vào frontend. Đăng nhập xong chuyển `/dashboard`.
Admin có thêm `/admin`; USER truy cập trang này được chuyển `/403`.

| API | Chức năng |
| --- | --- |
| `POST /api/v1/auth/login` | JSON `{ "identifier": "username hoặc email", "password": "..." }` |
| `POST /api/v1/auth/refresh` | Xoay refresh token bằng cookie và header CSRF |
| `POST /api/v1/auth/logout` | Thu hồi phiên tương ứng, xóa cookie, trả 204 |
| `GET /api/v1/auth/me` | Thông tin tài khoản hiện tại; Bearer access token |
| `GET /api/v1/admin/check` | Endpoint tối thiểu để kiểm thử quyền ADMIN |

POST auth yêu cầu `Origin` nằm trong `CORS_ORIGINS`. Khi có refresh cookie, refresh/logout
còn yêu cầu header `X-CSRF-Token` bằng cookie `smartrobot_csrf` và khớp hash đã lưu của phiên.
Frontend tự gửi các thông tin này. Gọi bằng HTTP client thủ công cũng phải tuân thủ Origin/CSRF;
đây không phải lỗi CORS cần khắc phục bằng wildcard.

Access JWT mặc định 15 phút, chỉ giữ trong memory. Refresh token opaque 384-bit, chỉ lưu
SHA-256 trong DB; cookie HttpOnly, host-only, SameSite=Lax, path `/api/v1/auth`. CSRF cookie
được JavaScript đọc, không chứa access/refresh token. Phiên có hạn tuyệt đối 7 ngày; refresh
không kéo dài hạn này. Reuse thu hồi cả family, bao gồm access tokens còn hạn của phiên đó.
Logout không thu hồi các lần đăng nhập khác của cùng tài khoản.

Production cần `ENVIRONMENT=production`, `COOKIE_SECURE=true`, `CORS_ORIGINS` là danh sách
origin HTTPS cụ thể và reverse proxy phục vụ frontend cùng `/api` trên một origin HTTPS.
Không dùng wildcard CORS. Cấu hình trusted proxy rõ ràng nếu triển khai sau proxy; IP limiter
dựa vào địa chỉ client do ASGI server cung cấp, không tự tin `X-Forwarded-For` từ request.

Login giới hạn theo IP và identifier trong PostgreSQL, dùng chung giữa API workers:
mặc định 30/IP và 10/identifier mỗi 300 giây, tính cả lần đăng nhập thành công.
HTTP 429 có `Retry-After`. Khóa cũ được dọn sau 1 ngày khi có request login.
Frontend dùng một refresh promise cho các request đồng thời; Web Locks hỗ trợ tuần tự hóa
rotation giữa các tab, BroadcastChannel truyền thông báo logout mà không truyền token.

## Quản trị người dùng và xe robot

Đăng nhập bằng ADMIN, mở `/admin/users` hoặc `/admin/robots` từ mục Quản trị.
Menu Tổng quan và Đăng xuất vẫn dùng authentication Phase 2. USER không truy cập được
các trang hoặc API Admin.

Người dùng: tìm kiếm username/email, lọc role/trạng thái, phân trang, thêm/sửa, đổi role,
kích hoạt/vô hiệu hóa và đặt lại mật khẩu trong dialog. Không xóa tài khoản. Không thể
tự vô hiệu hóa tài khoản hoặc hạ quyền Admin hoạt động cuối cùng. Vô hiệu hóa thu hồi mọi
auth session và đóng lease hiện tại; kích hoạt lại không khôi phục phiên cũ. Đặt lại mật khẩu
cũng thu hồi mọi auth session; nếu tự đặt lại mật khẩu, cần đăng nhập lại.

Xe robot: tìm kiếm tên/Device ID, lọc kết nối/trạng thái, phân trang, thêm/sửa, kích hoạt,
vô hiệu hóa và xoay credential. Device ID gồm 3–128 ký tự chữ/số/`_.:-`, phân biệt hoa thường.
Credential được cấp khi thêm xe và chỉ hiện một lần trong dialog có nút sao chép.
Đóng dialog sẽ xóa secret khỏi UI; muốn cấp lại phải xoay credential mới.

Xoay credential thu hồi secret cũ ngay, xóa heartbeat và đóng các lease hiện tại. Thiết bị
cần cấu hình lại; chức năng này chưa gửi lệnh vật lý đến ESP32. Vô hiệu hóa xe cũng xóa
heartbeat, đóng lease và từ chối device authentication. Đổi Device ID làm mất hiệu lực
kết nối/lease hiện tại; sửa riêng tên xe giữ nguyên thông tin kết nối.

Robot mới luôn Offline. Online yêu cầu heartbeat thực tế trong
`ROBOT_OFFLINE_AFTER_SECONDS` (mặc định 15 giây), active và timestamp không ở tương lai.
Busy yêu cầu thêm một lượt mượn chưa đóng, đã bắt đầu và chủ sở hữu đang active; lượt mượn mới không hết hạn.
Admin UI làm mới trạng thái mỗi 15 giây và có nút Làm mới. Chưa có heartbeat API ở Phase 3,
vì vậy robot mới vẫn Offline cho tới khi Device API được triển khai.

| Admin API | Chức năng |
| --- | --- |
| `GET /api/v1/admin/users` | `page`, `page_size`, `q`, `role`, `is_active` |
| `GET /api/v1/admin/users/{id}` | Chi tiết user |
| `POST /api/v1/admin/users` | Tạo user, password được hash Argon2id |
| `PATCH /api/v1/admin/users/{id}` | Sửa username/email |
| `PATCH /api/v1/admin/users/{id}/role` | Đổi USER/ADMIN |
| `PATCH /api/v1/admin/users/{id}/status` | Kích hoạt/vô hiệu hóa |
| `POST /api/v1/admin/users/{id}/reset-password` | Đặt mật khẩu mới, thu hồi phiên |
| `GET /api/v1/admin/robots` | `page`, `page_size`, `q`, `status`, `is_active` |
| `GET /api/v1/admin/robots/{id}` | Chi tiết robot, không có hash/secret |
| `POST /api/v1/admin/robots` | Tạo robot và cấp credential một lần |
| `PATCH /api/v1/admin/robots/{id}` | Sửa tên/Device ID |
| `PATCH /api/v1/admin/robots/{id}/status` | Kích hoạt/vô hiệu hóa |
| `POST /api/v1/admin/robots/{id}/credentials/rotate` | Xoay credential, chỉ trả secret mới một lần |

Mọi API trên yêu cầu Bearer JWT của ADMIN active. Pagination mặc định 20, giới hạn 100
records/trang và page 1–10000; `q` tối đa 254 ký tự. Robot status filter dùng `ONLINE`,
`OFFLINE`, `BUSY`. Danh sách trả `items`, `total`, `page`, `page_size`.
HTTP: tạo thành công 201, reset password 204, thiếu auth 401, thiếu quyền 403,
không tồn tại 404, xung đột/ràng buộc Admin 409, dữ liệu không hợp lệ 422.

Không thay đổi models hay thêm migration trong Phase 3; schema hiện có đủ cho chức năng này.
`alembic upgrade head` và `alembic check` vẫn phải chạy khi nghiệm thu. Thao tác ghi và audit
được commit trong cùng transaction. Xem [Báo cáo Phase 3](docs/phase-3-report.md) để kiểm thử UI.

## Dashboard và chi tiết xe

Sau login, `/dashboard` hiển thị card các xe đang kích hoạt, tìm theo tên, lọc
Online/Offline/Busy và phân trang 12 xe/trang. Nhấn **Xem xe** để mở `/robots/:id`;
xe Offline hoặc Busy vẫn xem được chi tiết. Header giữ tài khoản, Tổng quan, Đăng xuất
và mục Quản trị chỉ cho ADMIN.

Trang `/robots/:id` hiển thị tên, Device ID, trạng thái kết nối/kích hoạt và heartbeat cuối
theo UTC, cùng giao diện điều khiển Phase 5. Xe chưa kết nối vẫn Offline; backend không
tự tạo heartbeat hoặc xác nhận động cơ đã thực thi lệnh.

| API USER và ADMIN active | Tham số/chức năng |
| --- | --- |
| `GET /api/v1/robots` | `page`, `page_size`, `q` (tên xe), `status` |
| `GET /api/v1/robots/{robot_id}` | Chi tiết xe đang kích hoạt |

API yêu cầu Bearer JWT. Mọi user active có cùng quyền đọc các xe active; không có ACL
riêng từng xe. Pagination mặc định 20, tối đa 100/trang, page 1–10000; `q` tối đa 120
ký tự. `status`: `ONLINE`, `OFFLINE`, `BUSY`. Response list gồm `items`, `total`, `page`,
`page_size`; mỗi xe chỉ có `id`, `name`, `device_id`, `is_active`, `last_seen_at`, `status`,
`available`. `available=true` khi Online; đây là thông tin khả dụng, chưa cấp quyền điều khiển.
Không trả credential/hash, user sở hữu lease hoặc token.

Xe không tồn tại hoặc inactive trả cùng lỗi 404; UI hiển thị trang không tìm thấy xe.
UUID sai cú pháp trả 422 và cũng được UI detail xử lý như trang 404. List luôn lọc active,
kể cả khi client tự thêm query `is_active=false`. Response dùng `Cache-Control: no-store`.

Dashboard và metadata detail dùng TanStack Query polling 5 giây khi trang hiển thị, chia sẻ request
cùng query key và truyền AbortSignal tới API client. Rời trang/logout sẽ dừng polling,
hủy fetch đang chạy và xóa cache của phiên; detail dừng polling sau 404/UUID không hợp lệ.
Lỗi mạng có nút Thử lại và được thử lại ở interval tiếp theo khi trang đang hiển thị.
Card/trạng thái cũ được ẩn khi request lỗi, tránh trình bày dữ liệu đã lỗi như kết quả mới.

`RobotStatusService` được dùng chung cho Admin và USER, giữ ngưỡng
`ROBOT_OFFLINE_AFTER_SECONDS` từ Phase 3. Robot mới luôn Offline cho tới heartbeat hợp lệ
qua Device API Phase 6A; authenticate, lấy lệnh và telemetry không tự đánh dấu Online.

Hướng dẫn nghiệm thu và các phần chưa kiểm chứng: [Báo cáo Phase 4](docs/phase-4-report.md).

## Điều khiển và realtime

Mở `/robots/:id`, chọn **Nhận điều khiển** khi xe Online và chưa có lease. Một robot chỉ
có một lượt mượn, giữ cho tài khoản đến khi bấm **Trả xe** (`expires_at=null`). UI renew
theo khoảng backend trả về (mặc định 1,5 giây) để duy trì Auto permit, không gia hạn lượt mượn. Khi nhận lease, backend yêu cầu thiết bị xác nhận Manual
an toàn; chưa có xác nhận thì D-Pad bị khóa. Device API Phase 6A nhận ACK từ ESP32.

D-Pad chỉ gồm **Tiến, Lùi, Quay trái, Quay phải**; hỗ trợ chuột, cảm ứng, WASD và phím mũi tên.
Giữ nút gửi lệnh tuần tự, tối đa khoảng 4 lần/giây; nhả nút gửi STOP nội bộ. Không có nút Stop
hoặc Emergency Stop. Manual/Auto chỉ thể hiện yêu cầu; chế độ và chuyển động thiết bị chỉ
được hiển thị từ báo cáo đã xác thực của thiết bị. **Trả xe** gửi STOP rồi release. Tín hiệu động cơ là trạng thái đầu ra điện; xe chưa có encoder xác nhận bánh quay.

Mất focus, tab ẩn, mất WebSocket, lỗi lệnh, logout hoặc rời trang sẽ ngừng refresh
chuyển động và cố gắng STOP, vẫn giữ lượt mượn. Reload/login cùng tài khoản tự lấy lại quyền,
đổi secret để chặn credential cũ và yêu cầu handoff Manual an toàn. TTL lệnh Manual mặc định 700 ms; không phụ thuộc vào
cleanup frontend để chống lệnh tồn tại vô hạn. Auto dùng permit ngắn hạn, TTL mặc định 3 giây.
Firmware tương lai bắt buộc có watchdog cục bộ; backend không thể xác nhận động cơ dừng khi
chưa có ESP32 báo trạng thái thực tế. Không suy diễn khoảng cách, vật cản hoặc Buzzer từ thao tác người dùng.

| API dưới `/api/v1/robots/{id}/control` | Chức năng |
| --- | --- |
| `POST /acquire` | Cấp lease, trả secret một lần; 201 |
| `POST /renew`, `POST /release` | Gia hạn / trả quyền; 200 / 204 |
| `GET /session`, `GET /state` | Lease và trạng thái điều khiển |
| `POST /mode`, `POST /move`, `POST /stop` | Chấp nhận yêu cầu, chưa phải xác nhận thực thi; 202 |

REST dùng Bearer JWT, các thao tác sau acquire còn cần ID/secret của lease. Lease secret chỉ
ở memory; lệnh dùng UUID `request_id` và `client_sequence` để chống lặp/sai thứ tự. PostgreSQL
row locks, sequence/generation và unique constraints điều phối Move/Stop/Release/Mode.
Logout vô hiệu hóa lệnh cũ, giữ lượt mượn. Vô hiệu hóa user/robot hoặc xoay credential vẫn thu hồi quyền quản trị.

WebSocket `/api/v1/ws/robots/{id}` xác thực bằng frame đầu tiên; không có token trên URL.
Origin phải nằm trong `CORS_ORIGINS`. Backend gửi snapshot `robot.state` hoặc `ping` mỗi giây,
đọc PostgreSQL để hoạt động được với nhiều workers. UI reconnect có backoff, khóa điều khiển
trong lúc mất kết nối, giữ lượt mượn và reconnect để tiếp tục. Vite proxy đã bật WebSocket; production
reverse proxy cần hỗ trợ Upgrade và HTTPS/WSS. Không ghi auth frames vào proxy/application logs.

Migration mới **0003_control** kế thừa **0002_auth**: hai bảng control state/commands, auth
session binding và lifecycle triggers. Chạy `uv run alembic upgrade head` trước khi khởi động
bản mới. Lịch sử lệnh giới hạn mặc định 1000/robot, dọn lệnh kết thúc sau 7 ngày.

Chi tiết request, fencing, xác nhận chuyển mode và yêu cầu watchdog:
[Giao thức điều khiển](docs/robot-control-protocol.md).
Kết quả kiểm thử, danh sách file và cách nghiệm thu:
[Báo cáo Phase 5](docs/phase-5-report.md).

## Kết nối ESP32 thật — Phase 6A

ESP32 chạy Wi-Fi Station và HTTP Client, chủ động gọi laptop; backend không cần IP của
ESP32 và ESP32 không cần web server. Mỗi robot dùng Device ID/secret do Admin cấp một lần.
Mọi request Device API gửi `X-Device-ID`, `X-Device-Secret`; sau authenticate còn có
`X-Device-Session`. Không dùng User JWT, cookie hoặc credential trên URL.

| API prefix `/api/v1/devices` | Chức năng |
| --- | --- |
| `POST /authenticate` | Đăng ký boot UUID, trả device session và cấu hình thời gian |
| `POST /heartbeat` | Cập nhật heartbeat UTC, sequence chống replay |
| `GET /commands/current` | Lệnh hợp lệ + seq/gen, lease/authorization expiry hoặc null/STOP |
| `POST /commands/ack` | RECEIVED / APPLIED / REJECTED / FAILED, ghi thời gian và WS state |
| `POST /telemetry` | Lưu distance/obstacle/mode/movement/Buzzer thực tế vào PostgreSQL |

Lấy lệnh không đổi ACK. `APPLIED` là firmware báo đã chấp nhận áp dụng yêu cầu, không chứng
minh động cơ đã di chuyển. UI hiển thị xác nhận riêng và actual telemetry riêng; khi mất
kết nối không tiếp tục trình bày sensor/ACK cached như trạng thái live. D-Pad vẫn đúng bốn nút.

Heartbeat mặc định 2 giây, timeout 15 giây; command polling 100 ms. Telemetry tối đa 5 Hz
mặc định, retry duplicate không ghi thêm hoặc làm mới timestamp. Lưu tối đa 10000 mẫu/robot
và dọn mẫu cũ hơn 7 ngày theo batch. Reboot/session mới giữ lượt mượn và mode đang chọn, hủy lệnh cũ và yêu cầu handoff mới qua renew của người mượn.
Credential rotation/disable thu hồi cả device session. Không trả lệnh thuộc lease đã đóng,
kể cả STOP cũ; envelope `command=null`, `control_authorized=false` bắt buộc firmware dừng/hủy Auto.

Migration hiện tại **0005_persistent_borrow** cho phép lượt mượn không hết hạn và đổi trigger logout thành dừng lệnh, giữ lượt mượn. Các lượt mượn đang mở được chuyển sang `expires_at=null`. Chạy `uv run alembic upgrade head` trước khi chạy phiên bản này.

Mặc định Device API yêu cầu HTTPS; ESP32 phải kiểm tra CA và hostname chứng chỉ server.
Production không chấp nhận `DEVICE_ALLOW_INSECURE_HTTP=true`. Chỉ khi phát triển trong LAN
riêng mới bật biến này trong `.env`, dùng IP LAN của laptop và khởi động:

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers --no-access-log
```

Listener HTTP phát triển từ chối client IP công khai. Vẫn cần firewall chỉ cho LAN, không
port-forward/public Internet: HTTP truyền credential plaintext, không chống nghe lén/MITM.
Backend không cần IP thiết bị trong cấu hình; địa chỉ client chỉ dùng để giới hạn HTTP LAN.
Production đặt reverse proxy HTTPS/WSS, chỉ tin proxy đã cấu hình; không bật body/header logs.

Thông số cần nhập vào firmware: Wi-Fi SSID/password, base URL laptop (không dùng localhost
trên ESP32), CA/hostname, Device ID/secret lưu bảo mật, boot UUID mới, sequence/session và
timers theo response. Watchdog/motor/sensor/servo/Buzzer do Phase 6B thực hiện.
Không tạo project PlatformIO hoặc firmware trong Phase 6A.

Firmware **Phase 6B** hiện dùng project PlatformIO đã có: Wi-Fi Station/HTTPS, session,
heartbeat/poll/ACK/telemetry, L298N, HC-SR04, servo, Buzzer, relay, Manual/Auto state machine
và watchdog. GPIO giữ theo file .ino; cấu hình riêng trong NVS, mặc định motor chưa armed.
Hướng dẫn cấu hình/upload/monitor và giới hạn phần cứng tại [firmware/README.md](firmware/README.md),
kết quả build/kiểm thử tại [báo cáo Phase 6B](docs/phase-6b-report.md).

Hợp đồng JSON đầy đủ, lỗi/retry/reboot và curl:
[ESP32 Device API](docs/esp32-device-api.md).
Kết quả kiểm thử và file thay đổi: [Báo cáo Phase 6A](docs/phase-6a-report.md).

## Kiểm thử

Lần đầu tạo **database test riêng** bằng cấu hình development hiện có:

```bash
cd backend
uv run python -m scripts.prepare_test_database
```

Script chỉ tạo `smartrobot_test` nếu chưa tồn tại, giữ nguyên database development,
và tạo `.env.test` tại gốc repo với quyền `0600`. Role PostgreSQL cần quyền `CREATEDB`.
Nếu `.env.test` đã tồn tại, script dừng để giữ cấu hình đó. Có thể tự provision DB rồi
điền `.env.test` theo `.env.test.example`, hoặc truyền `TEST_DATABASE_URL` qua môi trường.

```bash
cd backend
uv run pytest -q
uv run ruff check app tests scripts migrations
uv run ruff format --check app tests scripts migrations
uv run alembic current
uv run alembic check
```

Tests từ chối database trùng tên với development, tên không kết thúc bằng `_test`,
hoặc URL chứa query parameters. Thiếu cấu hình test là lỗi, không bỏ qua integration tests.
Mỗi integration test tạo schema UUID riêng trong DB test, áp dụng Alembic, rồi chỉ dọn schema đó.
Tests có chạy downgrade, nhưng chỉ trong schema cô lập của DB test.

Kiểm thử không cần DB:

```bash
cd backend
uv run pytest -q -m 'not integration'
```

Kiểm tra frontend đã khởi tạo:

```bash
cd frontend
npm ci
npm test
npm run lint
npm run typecheck
npm run build
```

## Cấu trúc

```text
backend/
  app/
    api/routes/           # HTTP handlers
    core/                 # Environment settings
    db/                   # Declarative base, engine, session dependency
    models/               # users, robots, leases, telemetry, audit
    schemas/              # Pydantic response schemas
    repositories/         # Auth, rate limiting, user/robot queries và trạng thái
    services/             # Auth, quản trị, lease/commands, protocol adapter và cleanup
    websocket/            # Authenticated robot snapshots từ PostgreSQL
    main.py               # App factory, lifespan, router
  migrations/             # Alembic environment và revisions
  scripts/                # Provision database test riêng
  tests/                  # Unit tests và PostgreSQL integration tests
docs/backend-foundation.md
```

Thiết kế database, quy tắc transaction và giới hạn hiện tại:
[Backend Foundation](docs/backend-foundation.md).

Kết quả kiểm thử và danh sách file thay đổi:
[Báo cáo Phase 1](docs/phase-1-report.md).

Thiết kế authentication, kiểm thử và danh sách thay đổi Phase 2:
[Báo cáo Phase 2](docs/phase-2-report.md).

Quản trị người dùng và xe robot:
[Báo cáo Phase 3](docs/phase-3-report.md).

Dashboard và trang chi tiết xe:
[Báo cáo Phase 4](docs/phase-4-report.md).

Điều khiển và realtime:
[Báo cáo Phase 5](docs/phase-5-report.md), [Giao thức điều khiển](docs/robot-control-protocol.md).

Device Communication với ESP32 thật:
[Báo cáo Phase 6A](docs/phase-6a-report.md), [ESP32 Device API](docs/esp32-device-api.md).

Bản sửa firmware **6b-4**: relay GPIO26 cấp nguồn motor tự động, giữ Auto qua khôi phục mạng và retry HTTP: [chi tiết cập nhật/nghiệm thu](docs/fixes/motor-power-relay-and-auto-recovery.md).

Firmware **6b-5** giữ relay GPIO26 ON suốt lượt mượn, kể cả Manual idle/STOP và đổi mode; trả xe hoặc lỗi an toàn mới cắt nguồn. Cần backend mới có borrow ID trong snapshot idle: [hướng dẫn cập nhật](docs/fixes/borrow-powered-relay.md).

Firmware **6b-6** sửa Auto dừng vĩnh viễn sau khi quét vật cản: chọn hướng từ ngưỡng15cm,
đo lại sau quay và tiếp tục kiểm tra/quét khi bị chắn: [hướng dẫn Auto](docs/fixes/auto-obstacle-recovery.md).

Firmware **6b-7** sửa chiều quay theo OUT1/2 phải, OUT3/4 trái; Auto quét/rẽ/lùi tìm đường và cân PWM từng bánh qua Serial `trim`: [hướng dẫn cập nhật/cân bánh](docs/fixes/auto-backup-and-wheel-trim.md).

**6b-8** đảo lại pivot trái/phải của 6b-7 theo thử nghiệm thực tế người dùng báo; giữ nguyên tiến/lùi, trim và thuật toán Auto.

**6b-9** sửa Auto thành quét hai bên → chọn lối → lùi một lần → quay đúng lối đã chọn;
chặn lặp lùi khi vẫn kẹt và qua MODE/khôi phục kết nối:
[hướng dẫn cập nhật và kiểm thử](docs/fixes/auto-commit-backup-turn.md).

**6b-10** đối chiếu Auto với `ver2_6_esp32.ino`: ngưỡng rẽ15cm, lùi400ms, quay400ms,
hãm100ms trước/sau quay; giảm mức bù trái xuống85% để tiếp tục cân xe lệch phải.
Nhận diện bộ mặc định cũ trong NVS để áp dụng khi chỉ nạp app:
[chi tiết cập nhật](docs/fixes/auto-ver2_6-and-right-drift.md).

**6b-11** đặt trim trái100%/phải80% và sửa nhánh Auto không lùi khi cả hai bên chưa có lối:
lùi một lần rồi quét lại, tìm được hướng mới quay; vẫn chặn lùi liên tục.
[Chi tiết](docs/fixes/auto-backup-without-exit.md).

**6b-12** đặt trim trái100%/phải82%; Auto chốt hướng trước lùi, hết thời gian lùi
chuyển ngay sang quay dù phía trước vẫn dưới15cm. Không quét lại ở giữa:
[chi tiết](docs/fixes/auto-immediate-turn.md).

**6b-13** đặt trim trái100%/phải83,5%, hỗ trợ lưu hệ số thập phân. Servo quét chậm,
dừng ở từng bên lấy3 mẫu; chỉ quay về bên đủ trống, hai bên kín thì lùi lâu hơn và quét lại:
[chi tiết](docs/fixes/auto-slow-scan-side-turn.md).

**6b-14** chuyển Auto về logic ver2_6 (ưu tiên trái, lùi/hãm/quay và heuristic3 giây),
tích hợp với mode/permit/relay của web: [chi tiết](docs/fixes/auto-reference-web.md).
