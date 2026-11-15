# Phase 1 — Backend Foundation

## Phạm vi đã triển khai

SQLAlchemy 2, psycopg 3, Pydantic Settings, app factory FastAPI, health API,
migration Alembic và tests PostgreSQL thật. Các dependencies cần thiết đã có sẵn
trong môi trường ban đầu. Không khởi tạo lại backend/frontend hay Docker volumes.

## Database

Revision đầu tiên: `0001_foundation`, không có revision cha.

| Bảng | Dữ liệu và ràng buộc chính |
| --- | --- |
| `users` | UUID; username/email unique không phân biệt hoa thường; hash; role USER/ADMIN; active; timestamps |
| `robots` | UUID; device_id unique; credential hash; active; is_simulated; last_seen_at; timestamps |
| `control_sessions` | UUID; FK user/robot; lease hash unique; started/expires/ended; tối đa một lease chưa đóng mỗi robot |
| `robot_telemetry` | UUID; FK robot; khoảng cách nullable; mode/movement được giới hạn; recorded_at |
| `audit_logs` | UUID; FK user/robot nullable; action; JSONB metadata dạng object; created_at |

UUID được sinh tại ORM bằng `uuid4`; code SQL trực tiếp phải cấp UUID. Các timestamp dùng
`TIMESTAMPTZ`, server default `now()`, kết nối ứng dụng dùng UTC. `updated_at` được cập nhật
bởi SQLAlchemy khi ORM/SQLAlchemy phát UPDATE; SQL bên ngoài phải tự cập nhật trường này.
Không có trigger hoặc background worker trong Phase 1.

`role`, `mode`, `movement` dùng VARCHAR kèm CHECK constraint tại PostgreSQL. Dữ liệu rỗng,
expiry không hợp lệ và khoảng cách âm/NaN/vô hạn bị từ chối. Cảm biến lỗi được biểu diễn
bằng `distance_cm = NULL`, không được suy diễn thành khoảng cách an toàn.

Index phục vụ lịch sử theo robot/người dùng/thời gian, truy vấn heartbeat và dọn telemetry.
FK của sessions/telemetry dùng RESTRICT; audit dùng SET NULL để giữ sự kiện khi xóa entity.
Các API sau này sẽ vô hiệu hóa tài khoản/robot, không xóa lịch sử.

Hash columns chỉ lưu kết quả hash. Thuật toán Argon2, hashing credentials, refresh sessions,
device credential rotation và command sequencing sẽ được thêm ở phase tương ứng;
Phase 1 không cung cấp API tạo tài khoản, nhận secret hay cấp quyền điều khiển.

## Control lease: ràng buộc có sẵn và quy tắc cho Phase 5

Partial unique index `uq_control_sessions_open_robot` áp dụng khi `ended_at IS NULL`.
PostgreSQL từ chối hai giao dịch cùng commit lease chưa kết thúc cho cùng robot.
Tests thực hiện hai transaction trên hai connection đồng thời để kiểm tra ràng buộc này.
Không đưa `now()` vào điều kiện partial index vì thời gian trôi không tự cập nhật index.

Service acquire ở Phase 5 cần thực hiện trong một transaction:

1. Khóa dòng robot bằng `SELECT ... FOR UPDATE`.
2. Kiểm tra active/heartbeat, lấy thời gian DB sau khi đã có khóa.
3. Đóng lease hết hạn bằng `ended_at`; từ chối lease hiện còn hiệu lực.
4. Tạo lease mới và commit; xử lý unique conflict thành lỗi nghiệp vụ.

Lease hợp lệ phải có `ended_at IS NULL` **và** `expires_at > thời gian DB`.
Lease hết hạn vẫn chiếm unique slot cho tới khi được đóng; đây là lựa chọn an toàn,
ngăn cấp trùng nếu cleanup chậm. Các thao tác renew/release/command cần kiểm tra chủ sở hữu,
thời hạn và cùng phối hợp khóa robot. Phase 1 chỉ tạo ràng buộc và kiểm thử database,
chưa có API hoặc service thực thi giao thức acquire/renew/release.

## Heartbeat và retention: chính sách cho Phase 6

- `last_seen_at` là thời gian backend nhận heartbeat hợp lệ; NULL có nghĩa chưa thấy thiết bị.
- Online sẽ được suy ra từ `is_active` và heartbeat không quá 15 giây; không lưu cột online.
- Busy sẽ được suy ra từ lease hợp lệ, không lưu cờ độc lập dễ bị lệch trạng thái.
- Telemetry dự kiến giữ 7 ngày, dọn theo batch bằng cutoff trên `recorded_at` và index hiện có.
- Retention phải chạy qua job/CLI có lịch ở Phase 6; hiện chưa có telemetry ingestion hoặc job xóa.
- `is_simulated` phân biệt robot simulator với robot thật.

## Connection và transaction

Engine được tạo trong FastAPI lifespan và dispose khi dừng ứng dụng. Pool bật `pre_ping`;
pool size/overflow và timeout có thể cấu hình bằng environment variables. Mặc định connect/pool
timeout 5 giây, statement timeout 5 giây. Alembic dùng connection riêng với NullPool.

HTTP handlers đồng bộ dùng Session đồng bộ, không chạy truy vấn chặn trong async handler.
Dependency `get_db` đóng Session sau request và rollback phần chưa commit; service ở các phase
sau phải chủ động quyết định transaction/commit. Không có `create_all` hay migration tự chạy
trong startup. Lệnh migration lấy URL trực tiếp từ Settings, không ghi secret vào `alembic.ini`.

Settings đọc `.env` gốc, rồi `backend/.env`; biến môi trường hệ điều hành có ưu tiên cao hơn.
DATABASE_URL được che trong repr/lỗi settings. SQLAlchemy ẩn SQL parameters; readiness trả
lỗi 503 chung khi DB lỗi. Health routes là endpoint công khai duy nhất của ứng dụng Phase 1.

## Kiểm thử và an toàn dữ liệu

- Unit: settings, PostgreSQL URL validation, che secret và guard database test.
- HTTP: liveness, readiness 200 với DB thật, readiness 503 với kết nối lỗi, endpoint cũ, OpenAPI.
- Database: migration upgrade/downgrade/upgrade, idempotency và metadata drift bằng Alembic check.
- Dữ liệu: UUID, timestamp có timezone, updated_at, JSONB, defaults, unique/FK/CHECK và rollback.
- Lease: unique slot, hai transaction cạnh tranh, lease khác robot và thay lease hết hạn sau khi đóng.
- Telemetry: NULL cho sensor lỗi; từ chối số âm, NaN và vô hạn.
- Audit: giữ sự kiện khi FK entity bị xóa.

Mỗi test chỉ dọn schema `test_<uuid>` do chính nó tạo trong database riêng có đuôi `_test`.
Không test downgrade hoặc cleanup trên database development, không xóa Docker volumes.

## Giới hạn Phase 1

Chưa triển khai Auth/JWT, RBAC, user/robot CRUD, giao diện mới, realtime, control API,
command TTL/queue, watchdog, Device API, simulator hoặc firmware. Health readiness chỉ xác minh
kết nối DB. Các kiểm thử bảo mật và chức năng của những module đó sẽ được thêm theo phase,
không được xem các ràng buộc schema là một hệ thống điều khiển robot đã hoàn thiện.
