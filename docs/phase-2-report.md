# Phase 2 — Authentication & Authorization

Đã triển khai và kiểm tra ngày 15/11/2026 trên repository hiện có. Không khởi tạo lại
project hoặc database. Chỉ thực hiện Phase 2; chưa triển khai Phase 3.

## Chức năng đã hoàn thành

- Login bằng username/email, không phân biệt hoa thường; password Argon2id, dài 12–128 ký tự.
- Lỗi login chung cho tài khoản không tồn tại, sai password và tài khoản bị vô hiệu hóa.
- Rate limiting lưu tại PostgreSQL, dùng chung giữa workers: mặc định 30 lần/IP và
  10 lần/identifier trong 300 giây; tính cả lần thành công; trả 429 và `Retry-After`.
- Access JWT HS256: hạn mặc định 15 phút; `sub`, `sid`, `jti`, `iat`, `nbf`, `exp`,
  `iss`, `aud`, `type`; thuật toán, issuer, audience và claims được xác minh ở backend.
- Refresh token opaque ngẫu nhiên 384-bit; DB chỉ lưu SHA-256. Rotation trong transaction
  khóa dòng family; refresh cũ không được dùng lại. Reuse thu hồi cả family.
- Logout thu hồi phiên tương ứng; JWT của phiên đó cũng bị từ chối ngay, không cần chờ hết hạn.
- Phiên có hạn tuyệt đối 7 ngày; rotation không gia hạn thêm 7 ngày.
- Cookie refresh HttpOnly, host-only, SameSite=Lax, path `/api/v1/auth`;
  Secure bắt buộc trong production. CSRF cookie host-only, path `/`, được JavaScript đọc.
- Bảo vệ CSRF bằng Origin allowlist, header/cookie CSRF và hash CSRF gắn với family trong DB.
  CSRF token giữ ổn định trong family để tránh lỗi giữa các tab khi refresh.
- Các dependencies `get_current_user`, `get_current_active_user`, `require_role`, `require_admin`.
  Role và active status được lấy từ DB ở mọi request được bảo vệ, không lấy từ body hoặc tin role JWT.
- Validation errors được lọc bỏ input để tránh trả plaintext password trong JSON lỗi.
  Auth responses dùng `Cache-Control: no-store`; tokens được ẩn khỏi dataclass repr.
- CLI khởi tạo Admin đầu tiên: nhập password ẩn, xác nhận lại, khóa advisory chống bootstrap
  đồng thời, kiểm tra trùng username/email. Từ chối non-interactive input và getpass echo fallback.
- Login React/TypeScript/Tailwind/Lucide, tiếng Việt, hiện/ẩn password, validation, loading/error.
- AuthProvider, API client, ProtectedRoute, AdminRoute; dashboard/admin tối thiểu, trang 403, logout.
- Access token chỉ nằm trong module memory, không dùng localStorage/sessionStorage, URL hoặc logs.
- Tải lại trang khôi phục bằng refresh cookie rồi gọi `/me`; lỗi phiên chuyển về login.
- Một refresh promise dùng chung cho các request trong tab; Web Locks tuần tự hóa cookie mutation
  giữa các tab được hỗ trợ; BroadcastChannel thông báo logout, không gửi token qua channel.

Thiết kế Origin/custom header và token gắn với phiên được đối chiếu với
[OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
Cách pin thuật toán và xác minh JWT claims được đối chiếu với
[PyJWT Usage](https://pyjwt.readthedocs.io/en/stable/usage.html).

## Migration và dữ liệu

Revision mới: `0002_auth`, parent `0001_foundation`.

| Bảng | Mục đích |
| --- | --- |
| `auth_sessions` | Family theo lần login; user FK, hash CSRF, hạn tuyệt đối, revoked_at |
| `refresh_tokens` | Hash refresh token, session FK, rotated_at; unique hash và một token hiện hành/family |
| `login_rate_limits` | Key SHA-256 theo IP/identifier, attempts, window_started_at; atomic upsert |

Migration đã áp dụng vào development bằng `alembic upgrade head`. `alembic current`
trả `0002_auth (head)`; `alembic check` không phát hiện schema drift. Không xóa/reset
dữ liệu development hoặc Docker volumes; không thay đổi migration Phase 1.

Tests vẫn dùng database `smartrobot_test` và schema UUID riêng của Phase 1.
Chỉ cập nhật kỳ vọng danh sách bảng/revision trong test schema để bao gồm migration mới;
giữ nguyên các kiểm thử/ràng buộc Phase 1. Round-trip downgrade chỉ chạy trong DB test.

## API

| Method và endpoint | Quyền/yêu cầu | Kết quả chính |
| --- | --- | --- |
| `POST /api/v1/auth/login` | Origin được phép, JSON identifier/password | 200 token + cookies; 401, 422, 429 |
| `POST /api/v1/auth/refresh` | Origin, refresh cookie, CSRF header/cookie khớp family | 200 rotation; 401 hoặc 403 |
| `POST /api/v1/auth/logout` | Origin; CSRF khi có refresh cookie | 204; thu hồi phiên và xóa cookie |
| `GET /api/v1/auth/me` | Bearer JWT, phiên hợp lệ, user active | 200 thông tin user; 401 |
| `GET /api/v1/admin/check` | USER bị từ chối; ADMIN active | 200 hoặc 403; endpoint kiểm thử RBAC |

Response user chỉ gồm id, username, email, role, is_active. Không có password_hash hoặc
refresh token trong JSON. Không có endpoint đăng ký, reset password, user CRUD hoặc robot CRUD.

## Cách chạy và tạo Admin

JWT_SECRET của môi trường cục bộ đã được sinh ngẫu nhiên nếu chưa có, ghi vào `.env`
được git bỏ qua, quyền `0600`, không hiển thị giá trị. Không tạo Admin mặc định trong
database development trong phiên triển khai này.

```bash
# Từ gốc repository
docker compose up -d postgres
cd backend
uv sync --locked
uv run alembic upgrade head
uv run python -m scripts.create_admin
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers
```

CLI yêu cầu username, email và password nhập ẩn hai lần. Username: 3–64 ký tự chữ/số/`_.-`;
email hợp lệ; password 12–128 ký tự. CLI chỉ dùng cho Admin đầu tiên; nếu đã có Admin
hoạt động thì từ chối. Chức năng quản lý người dùng thuộc Phase 3.

```bash
# Terminal khác, từ gốc repository
cd frontend
npm ci
npm run dev
```

Mở `http://127.0.0.1:5173/login`, nhập tài khoản vừa tạo. Login thành công chuyển dashboard;
Admin có mục Quản trị. Vite proxy giữ Origin và chuyển `/api` đến backend port 8000.

Production cần `ENVIRONMENT=production`, `COOKIE_SECURE=true`, secret riêng và HTTPS origins
cụ thể trong `CORS_ORIGINS`. Frontend cùng `/api` được reverse proxy trên một HTTPS origin.
Không đưa JWT_SECRET vào biến `VITE_*`. Cấu hình proxy/IP trust rõ ràng khi triển khai.

## Kết quả kiểm thử thực tế

| Lệnh/kiểm tra | Kết quả |
| --- | --- |
| `uv run --locked pytest -q` | **90 passed**, 15.88 giây |
| `ruff check app tests scripts migrations` | Pass |
| `ruff format --check app tests scripts migrations` | Pass, 47 Python files |
| `uv run --locked alembic upgrade head` | Pass trên development |
| `uv run --locked alembic current` | `0002_auth (head)` |
| `uv run --locked alembic check` | Không có schema drift |
| `npm test` | **17 passed**, 2 test files |
| `npm run lint` | Pass |
| `npm run typecheck` | Pass |
| `npm run build` | Pass, TypeScript và Vite |
| `npm audit --audit-level=moderate` | **0 vulnerabilities** |
| HTTP thật qua Uvicorn + httpx | Login 200, me 200, USER admin 403, refresh 200, logout 204, JWT sau logout 401 |

Backend tests bao gồm username/email, sai password, user vô hiệu hóa, JWT hợp lệ/hết hạn/sai
signature, rotation/reuse, hai transaction refresh cùng token, logout theo phiên, RBAC và đổi
role từ DB, CSRF, Origin/CORS, Secure cookies, rate limiting và reset window, duplicate identity,
password hashing/validation, CLI và các tests Phase 1. Smoke-test Uvicorn dùng DB test cô lập,
tắt access logging và tự dừng server sau khi kiểm tra.

Frontend tests bao gồm render/hiện ẩn password, validation, login thành công/thất bại/loading,
protected/admin routes, restore, logout thành công/thất bại, expired session, React StrictMode,
refresh single-flight và nhiều request cùng nhận 401. Không chỉ kiểm tra render tĩnh.

## File thay đổi

Các file đã chỉnh sửa:

```text
.env.example
README.md
backend/pyproject.toml
backend/uv.lock
backend/app/main.py
backend/app/core/config.py
backend/app/api/router.py
backend/app/models/__init__.py
backend/tests/test_database.py
frontend/package.json
frontend/package-lock.json
frontend/index.html
frontend/public/favicon.svg
frontend/vite.config.ts
frontend/tsconfig.node.json
frontend/src/App.tsx
frontend/src/index.css
```

Các file đã thêm:

```text
backend/app/core/errors.py
backend/app/core/security.py
backend/app/models/auth.py
backend/app/schemas/auth.py
backend/app/repositories/auth.py
backend/app/services/auth.py
backend/app/services/bootstrap.py
backend/app/api/dependencies.py
backend/app/api/routes/auth.py
backend/migrations/versions/0002_auth_authentication_sessions_and_login_limits.py
backend/scripts/create_admin.py
backend/tests/test_auth.py
backend/tests/test_bootstrap.py
backend/tests/test_security.py
backend/tests/test_http_auth.py
frontend/vitest.config.ts
frontend/src/types/auth.ts
frontend/src/services/api.ts
frontend/src/contexts/auth-context.ts
frontend/src/contexts/AuthProvider.tsx
frontend/src/hooks/useAuth.ts
frontend/src/components/Loading.tsx
frontend/src/routes/AppRoutes.tsx
frontend/src/routes/ProtectedRoute.tsx
frontend/src/routes/AdminRoute.tsx
frontend/src/layouts/AppLayout.tsx
frontend/src/pages/LoginPage.tsx
frontend/src/pages/DashboardPage.tsx
frontend/src/pages/AdminPage.tsx
frontend/src/pages/ForbiddenPage.tsx
frontend/src/test/setup.ts
frontend/src/test/AuthFlow.test.tsx
frontend/src/test/api.test.ts
docs/phase-2-report.md
```

Đã bỏ `frontend/src/App.css` của Vite starter; thay bằng Tailwind/index.css.
`.env` cục bộ được bổ sung JWT_SECRET khi chưa có; không commit file này. Không chỉnh sửa
firmware, compose.yaml hoặc dữ liệu robot. Repository vẫn chưa có commit nền nên danh sách
này ghi nhận thay đổi của Phase 2, không đồng nhất với mọi file untracked trong `git status`.

## Lỗi đã xử lý và giới hạn còn lại

- Test repr của Phase 1 ban đầu thất bại vì tên field mới `jwt_secret` chứa từ `secret`.
  Đã đặt field này `repr=False`; không có secret thực tế bị in. Toàn bộ tests sau đó pass.
- Các lỗi Ruff import/format phát hiện trong quá trình triển khai đã sửa.
- npm audit ban đầu báo 7 moderate do minimatch trong TypeScript ESLint. Đã override
  minimatch `^11.0.8`, dedupe lockfile/dependency tree, chạy lại lint/tests/typecheck/build;
  audit cuối cùng trả 0. Override là thay đổi của dev tooling và có thể gỡ khi upstream cập nhật.
- **Chưa kiểm tra UI bằng trình duyệt thật**: công cụ browser inventory trả
  `The browser access host is unavailable`. Không có ảnh chụp hoặc xác nhận visual/mobile
  từ browser. Component tests, build và HTTP smoke-test đã chạy như ghi ở trên.
- Trình duyệt không hỗ trợ Web Locks chỉ được single-flight trong từng tab; refresh đồng thời
  giữa các tab trên những trình duyệt đó có thể kích hoạt reuse protection và cần đăng nhập lại.
  Backend vẫn từ chối reuse; không có grace window cho token cũ.
- Token đã rotate được giữ để phát hiện reuse. Chưa có scheduled job xóa auth history hết hạn;
  hạn sử dụng và thu hồi vẫn được kiểm tra từ DB ở mọi protected request.
- Chưa có đăng ký công khai, quản lý người dùng/robot, robot dashboard/control, WebSocket,
  Device API, simulator hoặc firmware. Các trang dashboard/admin hiện chỉ xác minh auth/RBAC.

Không còn lỗi kiểm thử được ghi nhận. Dừng tại Phase 2 để nghiệm thu.
