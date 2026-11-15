# Kết quả Phase 1

Kiểm tra ngày 15/11/2026 trên môi trường hiện có của repository.

## Kết quả đã chạy thực tế

| Kiểm tra | Kết quả |
| --- | --- |
| `uv run --locked pytest -q` | **38 passed**, 3.30 giây |
| `ruff check app tests scripts migrations` | Pass |
| `ruff format --check app tests scripts migrations` | Pass, 32 Python files |
| `uv run --locked alembic upgrade head` trên development | Pass, tạo 5 bảng nền tảng và bảng version |
| `uv run --locked alembic current` | `0001_foundation (head)` |
| `uv run --locked alembic check` trên development | Không phát hiện schema drift |
| `npm run build` | Pass, TypeScript và Vite |
| HTTP thực tế qua Uvicorn: `/api/v1/health` | 200, `{"status":"ok"}` |
| HTTP thực tế qua Uvicorn: `/api/v1/health/ready` | 200, `{"status":"ok","database":"ok"}` |
| HTTP thực tế qua Uvicorn: `/api/health` | 200 |

Uvicorn smoke-test đã được dừng sau khi kiểm tra. Không có server mới được để chạy nền.

Integration tests chạy trên database **smartrobot_test**, không chạy cleanup/downgrade
trên development. Test cạnh tranh lease dùng hai connection/transaction đồng thời,
kết quả một transaction commit và transaction còn lại bị unique conflict.
Migration round-trip và so sánh metadata cũng nằm trong bộ tests đã pass.

## File đã chỉnh sửa

- `.gitignore`: cho phép commit mẫu `.env.test.example`, tiếp tục bỏ qua secrets và artifacts.
- `backend/pyproject.toml`: khai báo trực tiếp python-dotenv, cấu hình pytest và Ruff.
- `backend/uv.lock`: cập nhật dependency trực tiếp tương ứng.
- `backend/app/main.py`: app factory, lifespan quản lý engine/session, versioned router.

## File đã thêm

```text
.env.example
.env.test.example
README.md
docs/backend-foundation.md
docs/phase-1-report.md
backend/alembic.ini
backend/app/api/__init__.py
backend/app/api/router.py
backend/app/api/routes/__init__.py
backend/app/api/routes/health.py
backend/app/core/__init__.py
backend/app/core/config.py
backend/app/db/__init__.py
backend/app/db/base.py
backend/app/db/session.py
backend/app/models/__init__.py
backend/app/models/audit_log.py
backend/app/models/control_session.py
backend/app/models/enums.py
backend/app/models/robot.py
backend/app/models/robot_telemetry.py
backend/app/models/user.py
backend/app/repositories/__init__.py
backend/app/schemas/__init__.py
backend/app/schemas/health.py
backend/app/services/__init__.py
backend/migrations/env.py
backend/migrations/script.py.mako
backend/migrations/versions/0001_foundation_backend_foundation.py
backend/scripts/__init__.py
backend/scripts/prepare_test_database.py
backend/tests/__init__.py
backend/tests/conftest.py
backend/tests/support.py
backend/tests/test_config.py
backend/tests/test_database.py
backend/tests/test_health.py
```

`.env.test` cũng được tạo cục bộ, quyền `0600`, được git bỏ qua; không ghi secrets vào báo cáo.
Build tạo artifacts trong `frontend/dist/`, được git bỏ qua. Source frontend, compose.yaml,
`.env` development, firmware hiện có và Docker volumes được giữ nguyên.

Repository ban đầu chưa có commit, các file hiện hữu đã ở trạng thái untracked;
không thể dùng `git diff` để phân biệt toàn bộ file có sẵn và file mới. Danh sách trên
ghi nhận các thay đổi do phiên triển khai này thực hiện, không phải mọi file untracked.

## Lỗi đã xử lý và giới hạn

Lần chạy tests đầu tiên: 37 pass, 1 fail do test dùng role vượt chiều dài VARCHAR và
kỳ vọng IntegrityError trong khi PostgreSQL trả DataError. Đã đổi giá trị role không hợp lệ
thành chuỗi vừa chiều dài để kiểm tra đúng CHECK constraint; toàn bộ 38 tests sau đó pass.
Các lỗi format ban đầu đã được sửa và Ruff pass.

Không còn lỗi kiểm thử được ghi nhận. Các lệnh cần truy cập Docker socket, uv cache
và PostgreSQL được chạy qua quyền thực thi được cấp của môi trường.

Chưa triển khai Phase 2 hoặc các phase sau. Chính sách heartbeat, retention và giao thức
cấp lease cho các phase sau được mô tả trong `backend-foundation.md`; hiện chỉ có schema,
ràng buộc DB và kiểm thử nền tảng, chưa có hệ thống điều khiển robot hoạt động.
