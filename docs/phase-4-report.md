# Phase 4 — User Dashboard & Robot Detail

Triển khai và kiểm thử ngày 15/11/2026 trên codebase hiện có. Đã đọc README và báo cáo
Phase 3, kiểm tra Auth/RBAC, Robot/ControlSession models, API quản trị, frontend routing,
layout và API client. Lần chạy đầu bị người dùng ngắt khi đang đọc source, chưa sửa code;
đã kiểm tra lại trạng thái repository trước khi tiếp tục.

## Chức năng đã hoàn thành

- API đọc danh sách và chi tiết robot cho mọi USER/ADMIN đang active, xác thực bằng JWT.
- Chỉ đọc xe đang kích hoạt; không thêm ACL riêng từng robot.
- Pagination, tìm kiếm theo tên, lọc ONLINE/OFFLINE/BUSY từ PostgreSQL.
- Response có last_seen_at, status, available; không có credential/hash, lease owner hoặc token.
- `RobotStatusService` dùng chung SQL calculation của Phase 3 cho cả Admin và USER:
  heartbeat còn hạn theo cấu hình, UTC, không nhận timestamp tương lai; Busy chỉ khi Online
  và có lease chưa đóng/đã bắt đầu/chưa hết hạn, owner active.
- Robot mới chưa có heartbeat vẫn Offline. Lease hết hạn/đã đóng không làm xe Busy.
- Dashboard `/dashboard`: tiêu đề Xe robot, search/filter, card responsive 1/2/3 cột và phân trang.
  Mỗi card gồm tên, trạng thái và link Xem xe; chỉ dùng Lucide Bot, không có ảnh thiết bị giả.
- Detail `/robots/:id`: tên, Device ID, trạng thái, heartbeat UTC, activation status, link Dashboard
  và dòng ngắn Chưa hỗ trợ điều khiển. Xe Offline/Busy vẫn xem được chi tiết.
- Giữ header/logout/AuthProvider/ProtectedRoute từ các phase trước; Quản trị chỉ hiện với ADMIN.
- Loading, Chưa có xe, Không thể tải dữ liệu, Thử lại, 404 và chuyển về Login khi hết phiên.

## API mới và chính sách dữ liệu

| Endpoint | Chức năng |
| --- | --- |
| `GET /api/v1/robots` | List active; page, page_size, q, status |
| `GET /api/v1/robots/{robot_id}` | Chi tiết active robot |

Page mặc định 1, page_size mặc định 20, giới hạn 100/trang, page tối đa 10000.
UI dùng 12 xe/trang. `q` tối đa 120 ký tự, trim và tìm không phân biệt hoa thường theo **tên**;
không tìm theo Device ID ở API USER. Ký tự wildcard được escape để tìm literal.
Status filter dùng uppercase `ONLINE`, `OFFLINE`, `BUSY`.

Mỗi robot chỉ trả:

```text
id, name, device_id, is_active, last_seen_at, status, available
```

`available` tính từ `is_active && status == ONLINE`, không phải control lease hoặc lời hứa
robot vẫn khả dụng ở một request sau. Phase 5 phải kiểm tra/cấp lease trong transaction riêng.

Robot không tồn tại và robot inactive trả cùng lỗi **404**, giúp giữ phạm vi USER chỉ thấy xe
active. UUID sai cú pháp trả 422 của Pydantic; UI detail xử lý thành trang không tìm thấy.
Client không thể mở rộng phạm vi bằng query `is_active=false`. Thiếu/hết hạn auth hoặc tài khoản
inactive trả 401 theo Phase 2. Response thành công và lỗi dùng `Cache-Control: no-store`.

Detail lấy robot active và trạng thái trong cùng một SELECT; không lấy danh sách robot từ mock
hoặc cấu hình frontend. Response schema dùng allowlist tường minh để không lộ trường ORM nội bộ.

## Polling, cleanup và trạng thái UI

- `useRobots` và `useRobot` dùng TanStack Query, interval 5000 ms, không poll khi page mất focus.
- Query key gồm user ID, loại query, ID robot hoặc page/filter. Hai observer cùng key chia sẻ request.
- Cache staleTime 4000 ms; quay lại Dashboard trong khoảng cache còn mới không gọi list lần nữa.
- Search chỉ gửi khi nhấn Tìm/Enter; thay filter gửi query mới và đưa page về 1.
- `RobotDataLayout` tạo query scope theo user ID cho Dashboard/detail. Rời scope/logout sẽ clear
  cache, gỡ observer/timer và abort request qua AbortSignal; không dùng setInterval tự quản lý.
- API client kiểm tra signal trước fetch và trước refresh/retry; query đã hủy không khởi tạo
  refresh token hoặc gửi lại request. Refresh single-flight của Phase 2 được giữ nguyên.
- Không retry dồn dập; lỗi mạng có nút Thử lại và polling tiếp ở interval sau. Khi lỗi, ẩn card/detail
  cached để không trình bày status cũ như kết quả mới.
- Sau 404/422, detail dừng polling, refetch-on-focus/reconnect; người dùng quay lại Dashboard.
- Không lưu token hoặc robot data vào localStorage/sessionStorage, không log credentials/tokens.
- `available` không dùng để dựng nút điều khiển; UI chỉ xem xe ở phase này.

## Components và tái sử dụng

Mới: `RobotCard`, `RobotStatus`, `RobotFilters`, `RobotDetailPage`, `RobotDataLayout`,
`robotService`, hooks `useRobots`/`useRobot`, types `UserRobot`/`RobotStatusValue`.

Tái dùng AuthProvider, ProtectedRoute, AppLayout, API client, Pagination, ListControls,
Feedback, styles/button/badges và RobotRepository. Feedback hỗ trợ tùy chỉnh text nhưng giữ
defaults của Admin; ListControls hỗ trợ giới hạn search riêng. Admin robot table dùng cùng
RobotStatus badge với Dashboard. Không thay thế auth hoặc viết lại Admin management.

## Database và migration

Không sửa bảng SQLAlchemy, thêm cột, tạo migration, reset database hoặc xóa Docker volumes.
Chỉ chuyển enum Python `RobotStatus` từ schema Admin sang domain enums để tái sử dụng;
schema Admin vẫn re-export enum đó để giữ tương thích import hiện có.

Head vẫn **0002_auth**. `alembic check` không phát hiện upgrade operations/schema drift.
Settings `ROBOT_OFFLINE_AFTER_SECONDS` và `.env.example` từ Phase 3 đã đủ dùng, không cần biến mới.

Không tạo user/robot/heartbeat giả trong development. Tests dùng database smartrobot_test,
schema UUID riêng, fixtures/mocks chỉ trong thư mục tests. Không chỉnh firmware hoặc secrets.

## Kết quả kiểm thử thực tế

| Kiểm tra | Kết quả |
| --- | --- |
| `uv run --locked pytest -q` | **160 passed**, 44.15 giây |
| `ruff check app tests scripts migrations` | Pass |
| `ruff format --check app tests scripts migrations` | Pass, 63 Python files |
| `uv run --locked alembic check` | Không có schema drift |
| `uv run --locked alembic current` | `0002_auth (head)` |
| `npm test` | **60 passed**, 5 test files |
| `npm run lint` | Pass |
| `npm run typecheck` | Pass |
| `npm run build` | Pass |
| HTTP thật: Uvicorn + httpx | List/detail 200; thiếu auth 401; inactive/missing 404; không có credential |

Backend giữ toàn bộ tests Phase 1–3, thêm 25 cases gồm USER/ADMIN access, unauthenticated/
disabled user, robot active-only, bounded/stable pagination, name search, status filtering trước
pagination, Online/Offline/Busy, lease hết hạn/đã đóng, stale/future heartbeat, timeout cấu hình,
UTC, allowlist dữ liệu, không tồn tại, thay đổi heartbeat và status parity giữa Admin/USER.
Tests cũng xác minh không có mutation/control endpoint mới. HTTP smoke-test mở Uvicorn thật trên
port tạm, dùng test database, tắt access log và tự dừng server sau kiểm tra.

Frontend giữ các test cases auth/Admin cũ. Chỉ cập nhật title assertion Tổng quan → Xe robot
và thêm mock response robot list trong AuthFlow để phù hợp Dashboard mới; không bỏ kiểm tra
login/restore/logout/protected/admin routes.

Tests mới bao gồm cards/status, search/filter, pagination, empty/loading/error/retry,
view Offline/Busy, navigation sang detail/quay lại cache, 404, auth gate, Admin nav, abort khi
logout, polling list/detail sau 5 giây, unmount cleanup, concurrent observer dedupe, in-flight
abort, dừng poll sau 404, pause khi unfocused và phục hồi network error ở interval tiếp theo.
API client có thêm tests request đã abort không gửi fetch hoặc refresh/retry.

## File thay đổi

Đã sửa:

```text
README.md
backend/app/models/enums.py
backend/app/schemas/admin.py
backend/app/repositories/admin.py
backend/app/api/router.py
frontend/src/pages/DashboardPage.tsx
frontend/src/routes/AppRoutes.tsx
frontend/src/services/api.ts
frontend/src/types/admin.ts
frontend/src/pages/admin/RobotsPage.tsx
frontend/src/components/admin/Feedback.tsx
frontend/src/components/admin/ListControls.tsx
frontend/src/test/AuthFlow.test.tsx
frontend/src/test/api.test.ts
```

Đã thêm:

```text
backend/app/services/robot_status.py
backend/app/services/robots.py
backend/app/schemas/robots.py
backend/app/api/routes/robots.py
backend/tests/test_user_robots.py
backend/tests/test_http_user_robots.py
frontend/src/types/robots.ts
frontend/src/services/robotService.ts
frontend/src/hooks/useRobots.ts
frontend/src/layouts/RobotDataLayout.tsx
frontend/src/components/robots/RobotCard.tsx
frontend/src/components/robots/RobotStatus.tsx
frontend/src/components/robots/RobotFilters.tsx
frontend/src/pages/RobotDetailPage.tsx
frontend/src/test/UserDashboard.test.tsx
frontend/src/test/RobotPolling.test.tsx
docs/phase-4-report.md
```

Không thêm dependencies hoặc sửa lockfiles, không xóa file. Repository chưa có commit nền;
danh sách này ghi nhận thay đổi của Phase 4, không phải mọi file untracked trong git status.

## Hướng dẫn kiểm tra Dashboard bằng trình duyệt

```bash
# Terminal 1, từ gốc repo
cd backend
uv sync --locked
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers

# Terminal 2, từ gốc repo
cd frontend
npm ci
npm run dev
```

1. Đăng nhập tại `http://127.0.0.1:5173/login`. Nếu chưa có Admin, dùng CLI Phase 2
   `uv run python -m scripts.create_admin` từ backend, nhập password ẩn.
2. Nếu chưa có xe, Dashboard phải hiện Chưa có xe. Admin có thể thêm xe bằng trang Phase 3
   `/admin/robots`; không tạo heartbeat giả để ép Online.
3. Quay Dashboard, xác nhận card tên xe, trạng thái Offline và link Xem xe. USER không thấy
   menu Quản trị; ADMIN thấy menu đó.
4. Tìm theo tên, lọc trạng thái, thử phân trang khi có hơn 12 xe. View Offline/Busy là link xem,
   không có acquire lease hoặc nút điều khiển.
5. Mở detail, kiểm tra tên/Device ID, trạng thái kích hoạt, heartbeat cuối hoặc Chưa kết nối,
   thông báo Chưa hỗ trợ điều khiển và link Về Dashboard.
6. Ở tab/profile Admin khác, sửa tên xe; Dashboard/detail hiện tên mới ở lần poll tiếp theo
   khi đang hiển thị. Disable xe: list loại bỏ xe và detail chuyển trang không tìm thấy sau poll.
7. Dùng DevTools Network offline để kiểm tra Không thể tải dữ liệu và Thử lại; online trở lại
   để kiểm tra phục hồi. Chuyển tab/rời trang/logout để kiểm tra không còn polling cũ.
8. Thử mobile/tablet/desktop và keyboard navigation. Các bước browser này cần người nghiệm thu
   chạy vì browser host của agent hiện không hoạt động.

## Lỗi đã sửa và phần chưa kiểm chứng

- TypeScript ban đầu báo TS2339 trong test helpers do signal được gán trong callback và suy luận
  thành never. Đã sửa holder có type tường minh; frontend tests/typecheck/build chạy lại pass.
- Các lỗi Ruff import/format phát hiện khi viết code đã được sửa; checks cuối pass.
- **Chưa kiểm thử visual/responsive bằng browser thật**: inventory trả
  `The browser access host is unavailable`. Không có screenshot hoặc xác nhận UI thực tế.
- Polling tests dùng TanStack Query thật với fake timers/focus manager trong jsdom; chúng không
  thay thế kiểm tra scheduling/visibility trên browser thực tế.
- Chưa có thiết bị gửi heartbeat, Device API hoặc simulator. Online/Busy được kiểm thử bằng
  dữ liệu trong DB test và mocks test; robot mới trong ứng dụng vẫn Offline.
- Vẫn giữ giới hạn auth history cleanup/cross-tab fallback của Phase 2 và Device Communication
  của Phase 3; không mở rộng các phần đó trong Phase 4.

Không còn lỗi kiểm thử được ghi nhận. Không triển khai Manual/Auto, Control Lease API,
WebSocket, Device API, Simulator hoặc firmware. Dừng tại Phase 4 để nghiệm thu.
