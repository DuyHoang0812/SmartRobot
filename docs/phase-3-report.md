# Phase 3 — User & Robot Management

Triển khai và kiểm thử ngày 15/11/2026 trên repository SmartRobot hiện có. Đã đọc README,
báo cáo Phase 1–2 và kiểm tra models, migrations, authentication/RBAC, frontend routing/API client.
Không khởi tạo lại môi trường. Dừng tại Phase 3.

## Chức năng hoàn thành

### Người dùng

- Danh sách có tìm kiếm username/email, lọc role/active và phân trang; chi tiết user.
- Thêm user bằng password Argon2id; sửa username/email; đổi role USER/ADMIN.
- Kích hoạt/vô hiệu hóa, đặt lại mật khẩu. Không có hard delete hoặc đăng ký công khai.
- Pydantic validation: username 3–64 ký tự chữ/số/`_.-`, email hợp lệ,
  password 12–128 ký tự; PATCH từ chối null, body rỗng và field ngoài phạm vi.
- Unique không phân biệt hoa thường theo indexes PostgreSQL Phase 1; xung đột trả 409.
- Chỉ ADMIN active được dùng mọi Admin endpoint; không tin role hoặc user ID trong body.
- Không thể tự vô hiệu hóa tài khoản. Không thể hạ quyền hoặc vô hiệu hóa Admin active cuối cùng.
- Khóa advisory PostgreSQL được chia sẻ với bootstrap CLI và mọi user mutation;
  xác minh lại actor sau khi có khóa. Hai Admin tự hạ quyền đồng thời chỉ một người thành công.
- Vô hiệu hóa thu hồi tất cả auth sessions và đóng lease của user trong cùng transaction.
  Reactivate không khôi phục phiên đã thu hồi. Password reset cũng thu hồi tất cả auth sessions.
- Login khóa dòng user để phối hợp với disable/reset password; không để một login đang chạy
  tạo auth session mới sau khi thao tác thu hồi đã hoàn tất.
- Đổi role có hiệu lực qua kiểm tra role từ DB của Phase 2; không cần tin claim role ở JWT.
  Frontend tải lại `/me` khi sửa tài khoản đang dùng; self password reset yêu cầu đăng nhập lại.

### Robot và credentials

- Danh sách có tìm kiếm tên/Device ID, lọc trạng thái kích hoạt/kết nối và phân trang.
- Thêm robot, xem chi tiết, sửa tên/Device ID, kích hoạt/vô hiệu hóa và xoay credential.
- Device ID duy nhất, phân biệt hoa thường, 3–128 ký tự chữ/số/`_.:-`.
- Không có API xóa robot hoặc cho phép Admin tự đặt heartbeat, status Online hay hash credential.
- Robot mới active nhưng **Offline**, `last_seen_at = NULL`.
- Online: active, heartbeat trong 15 giây mặc định và không ở tương lai.
- Busy: Online và có lease chưa đóng, đã bắt đầu, chưa hết hạn, user sở hữu còn active.
  Robot inactive hoặc heartbeat cũ luôn Offline, kể cả khi còn dòng lease chưa đóng.
- Cấu hình ngưỡng heartbeat bằng `ROBOT_OFFLINE_AFTER_SECONDS` (1–300 giây).
- Credential 384-bit ngẫu nhiên, DB chỉ lưu `sha256:<digest>` trong cột đã có;
  hash và secret không xuất hiện trong list/detail/audit.
- POST tạo xe cấp secret lần đầu. POST rotate cấp secret mới và thay hash ngay trong transaction.
  Secret cũ bị từ chối ngay, không có grace period. Không có API đọc lại secret đã cấp.
- Rotate xóa heartbeat và đóng lease; disable cũng vô hiệu hóa kết nối/lease hiện tại.
  Enable lại yêu cầu heartbeat mới. Đổi Device ID xóa heartbeat/lease; credential hiện tại
  chỉ xác thực được với Device ID mới. Sửa riêng tên xe không làm mất kết nối.
- `authenticate_device(db, device_id, secret)` dùng so sánh constant-time, kiểm tra active
  và khóa dòng robot. Phase 6 phải giữ cùng transaction/khóa tới khi ghi heartbeat/telemetry;
  service không tự cập nhật heartbeat hoặc commit. Không tạo Device Communication API ở phase này.

### Admin UI

- Navigation responsive, header/logout của Phase 2, sidebar/tab Người dùng và Xe robot.
- `/admin` giữ endpoint kiểm tra RBAC; `/admin/users` và `/admin/robots` là trang quản trị thực tế.
- Bảng, search, filters, pagination, nút refresh, loading/error/empty states và thông báo kết quả.
- Dialog thêm/sửa, thay đổi role/status, reset password và xác nhận rotate.
- Password input ẩn, xác nhận lại password; không hiển thị password hiện tại.
- Credential dialog chỉ hiện sau create/rotate, có cảnh báo một lần và nút sao chép.
  Đóng dialog bỏ secret khỏi state. Secret không đi qua localStorage, sessionStorage,
  URL, logs, TanStack Query cache hoặc mutation cache.
- TanStack Query chỉ cache dữ liệu danh sách đã được backend lọc; Admin cache được clear
  khi rời layout. Robot list refresh mỗi 15 giây; không dùng WebSocket.
- UI không có nút điều khiển robot hoặc dashboard card xe dành cho USER.

## API

Prefix `/api/v1/admin`; mọi endpoint dưới đây cần Bearer JWT của ADMIN active.
Tất cả response Admin dùng `Cache-Control: no-store`. CORS đã cho phép PATCH với origin
cụ thể/credentials của Phase 2; không dùng wildcard.

| Method | Path | Nội dung |
| --- | --- | --- |
| GET | `/users` | page, page_size, q, role, is_active |
| GET | `/users/{id}` | Chi tiết user |
| POST | `/users` | username, email, password, role (mặc định USER); 201 |
| PATCH | `/users/{id}` | username và/hoặc email |
| PATCH | `/users/{id}/role` | role USER/ADMIN |
| PATCH | `/users/{id}/status` | is_active boolean |
| POST | `/users/{id}/reset-password` | password mới; 204 |
| GET | `/robots` | page, page_size, q, status, is_active |
| GET | `/robots/{id}` | Robot đã lọc bỏ credential/hash |
| POST | `/robots` | name, device_id; 201, trả robot + credential một lần |
| PATCH | `/robots/{id}` | name và/hoặc device_id |
| PATCH | `/robots/{id}/status` | is_active boolean |
| POST | `/robots/{id}/credentials/rotate` | Trả robot + credential mới một lần |

Pagination mặc định 20/trang, giới hạn 100; page 1–10000, search tối đa 254 ký tự.
List trả `items`, `total`, `page`, `page_size`. Robot status filter dùng uppercase
`ONLINE`, `OFFLINE`, `BUSY`. Search escape ký tự wildcard `%`/`_` để tìm literal.

Lỗi nhất quán qua AppError: 401 chưa xác thực, 403 thiếu quyền, 404 không tồn tại,
409 xung đột identity/Device ID hoặc vi phạm quy tắc Admin, 422 validation.
AuthError kế thừa AppError để giữ nguyên behavior Phase 2. Không trả driver errors hoặc secret.

## Database, transaction và audit

**Không thêm hoặc sửa SQLAlchemy models/migration.** Các cột và indexes hiện có đủ dùng.
Head vẫn `0002_auth`, parent `0001_foundation`. Đã chạy `alembic upgrade head`, `current`
và `check` trên development; không có DDL mới hoặc schema drift.

Tái sử dụng users, robots, control_sessions, auth_sessions và audit_logs. User mutations
khóa membership + dòng user; robot mutations khóa dòng robot. Thay đổi dữ liệu, thu hồi
session/lease và audit commit cùng transaction. Lỗi unique rollback toàn bộ, bao gồm
heartbeat/lease đã chuẩn bị vô hiệu hóa khi đổi Device ID.

Audit actions: `user.created`, `user.updated`, `user.role_changed`, `user.disabled`,
`user.enabled`, `user.password_reset`, `robot.created`, `robot.updated`, `robot.disabled`,
`robot.enabled`, `robot.credential_rotated`. Audit lưu actor, robot hoặc target_user_id,
field names thay đổi, role trước/sau; không lưu password, credential, hash hoặc token.

Không reset DB, không xóa volumes, không tạo test records trong development. Các tests
dùng `smartrobot_test` với schema UUID riêng và cleanup theo cơ chế Phase 1.

## Kết quả kiểm thử thực tế

| Kiểm tra | Kết quả |
| --- | --- |
| `uv run --locked pytest -q` | **135 passed**, 36.79 giây |
| Ruff check | Pass |
| Ruff format check | Pass, 57 Python files |
| `alembic upgrade head` | Pass; không cần migration mới |
| `alembic current` | `0002_auth (head)` |
| `alembic check` | Không có upgrade operations/schema drift |
| `npm test` | **35 passed**, 3 test files |
| `npm run lint` | Pass |
| `npm run typecheck` | Pass |
| `npm run build` | Pass |
| Audit khi npm install dependency mới | 0 vulnerabilities |
| HTTP thật qua Uvicorn + httpx | Login Admin; create/role/disable user; create/rotate/list robot: pass |

Các tests Phase 1–2 được giữ và chạy cùng tests mới. Backend bổ sung kiểm tra từng Admin
mutation bị USER từ chối, unique/validation, role/last Admin/self-disable, thu hồi phiên
sau disable/reactivate/reset password, race login–revocation, race hai Admin tự demote,
robot Offline mặc định, heartbeat cũ/tương lai, lease hết hạn, credential cũ mất hiệu lực,
audit không chứa secrets, rollback connection/lease khi sửa Device ID trùng và CORS PATCH.

Frontend bổ sung kiểm thử layout, list/create/edit user, role/status/password dialog,
search/filter/pagination, list/create/edit/disable robot, cảnh báo rotate, one-time secret,
copy/close, loading/error/retry/empty và USER bị từ chối ở cả hai Admin routes.

## File thay đổi

Đã sửa:

```text
.env.example
README.md
backend/app/core/config.py
backend/app/core/errors.py
backend/app/main.py
backend/app/api/dependencies.py
backend/app/api/router.py
backend/app/repositories/auth.py
backend/app/services/bootstrap.py
frontend/package.json
frontend/package-lock.json
frontend/src/contexts/auth-context.ts
frontend/src/contexts/AuthProvider.tsx
frontend/src/layouts/AppLayout.tsx
frontend/src/routes/AppRoutes.tsx
frontend/src/index.css
frontend/src/test/setup.ts
```

Đã thêm:

```text
backend/app/db/locks.py
backend/app/schemas/admin.py
backend/app/repositories/admin.py
backend/app/services/admin_users.py
backend/app/services/admin_robots.py
backend/app/services/device_credentials.py
backend/app/api/routes/admin_users.py
backend/app/api/routes/admin_robots.py
backend/tests/test_admin.py
backend/tests/test_http_admin.py
frontend/src/types/admin.ts
frontend/src/hooks/useAdminList.ts
frontend/src/layouts/AdminLayout.tsx
frontend/src/components/admin/Modal.tsx
frontend/src/components/admin/ListControls.tsx
frontend/src/components/admin/Feedback.tsx
frontend/src/components/admin/UserDialog.tsx
frontend/src/components/admin/RobotDialog.tsx
frontend/src/components/admin/CredentialDialog.tsx
frontend/src/pages/admin/UsersPage.tsx
frontend/src/pages/admin/RobotsPage.tsx
frontend/src/test/AdminManagement.test.tsx
docs/phase-3-report.md
```

Dependency mới: `@tanstack/react-query`. Không bổ sung backend dependencies. Không xóa file,
không đổi secrets/môi trường cục bộ, không chỉnh firmware. Repository chưa có commit nền;
mọi file untracked trong git status không đồng nghĩa đều là thay đổi của Phase 3.

## Hướng dẫn nghiệm thu Admin UI

```bash
# Terminal 1, từ gốc repo
cd backend
uv sync --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers

# Terminal 2, từ gốc repo
cd frontend
npm ci
npm run dev
```

1. Nếu chưa có Admin active, chạy CLI Phase 2 `uv run python -m scripts.create_admin`
   từ backend và nhập password ẩn. Không có tài khoản mặc định.
2. Đăng nhập tại `http://127.0.0.1:5173/login`; mở Quản trị → Người dùng.
3. Thêm user, thử username/email trùng, sửa thông tin, đổi role, tìm/lọc và phân trang.
4. Thử hạ quyền Admin active cuối cùng và tự disable: backend phải từ chối.
5. Đăng nhập user ở trình duyệt/profile khác; disable user từ Admin. Request bảo vệ tiếp theo
   của user phải bị từ chối. Enable lại vẫn phải đăng nhập mới. Reset password cũng kết thúc phiên cũ.
6. Mở Xe robot, thêm xe bằng Device ID mới. Xe phải Offline/Chưa kết nối.
7. Sao chép secret trong dialog rồi đóng; list/detail không hiển thị lại secret.
8. Sửa tên, disable/enable, tìm/lọc xe. Thử Device ID trùng: nhận lỗi, dữ liệu cũ được giữ.
9. Xoay credential: đọc cảnh báo, xác nhận, lưu secret mới. Secret cũ không còn hợp lệ
   theo `authenticate_device`; chưa có public Device API để xác thực từ ESP32 trong phase này.
10. Đăng nhập bằng USER và thử `/admin/users`, `/admin/robots`: hiển thị 403;
    gọi API Admin bằng JWT USER phải trả 403.

## Chưa kiểm chứng và giới hạn

- Browser inventory vẫn trả `The browser access host is unavailable`. Chưa nghiệm thu visual,
  responsive thực tế, native dialog focus/keyboard trap hoặc clipboard permission trên browser thật.
  Component tests dùng jsdom và polyfill `showModal`; không coi chúng là browser visual tests.
- Chưa kết nối ESP32 thật; status tests seed heartbeat/lease trong DB test. Admin không thể
  tạo heartbeat qua API; thiết bị mới vẫn Offline vì Device Communication API chưa triển khai.
- Disable/rotate làm mất hiệu lực trạng thái và lease ở backend, không gửi lệnh dừng vật lý
  đến ESP32. Watchdog, command TTL và giao tiếp thiết bị thuộc các phase sau.
- API chỉ lưu hash hiện hành; nếu đóng dialog hoặc mất response chứa credential thì phải
  rotate mới, không thể khôi phục plaintext. Credentials cũ không đúng định dạng hiện hành
  cần được cấp lại qua rotate trước khi dùng service ở Phase 6.
- Robot list dùng polling 15 giây; chưa có realtime/WebSocket. Auth history cleanup từ Phase 2
  và firmware vẫn nằm ngoài phạm vi hiện tại.

Không còn lỗi kiểm thử được ghi nhận. Các lỗi import/format phát hiện trong quá trình viết
code đã được sửa và kiểm tra lại. Không bắt đầu Phase 4.
