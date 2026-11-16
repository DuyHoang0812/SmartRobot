# Sửa mất quyền điều khiển do STOP / ACK conflict — firmware 6b-2

Người dùng ghi nhận ACK409 lặp lại, sau đó renew/stop/release403 và Serial báo Device
session established lần nữa trong cùng uptime. Đọc DB chỉ SELECT xác nhận lease đã được
renew, vẫn còn hạn khi boot/session thiết bị mới đăng ký và thu hồi lease cũ. Có telemetry
SENSOR_ERROR ở một phiên Auto; log cũ chưa đủ phân biệt tất cả trigger firmware.

## Nguyên nhân trong source

- Hook frontend gọi STOP khi canDrive=false ngay cả không có Manual intent đang giữ.
  Khi chuyển Manual→Auto, pending/disabled hoặc cleanup D-Pad có thể phát STOP sau MODE,
  vô hiệu hóa MODE vừa gửi. Bắt đầu mỗi MOVE cũng phát STOP dù trước đó đã đứng yên.
- Firmware coi ACK409/telemetry409 ở Auto là lý do reset toàn bộ device session. 409 có
  thể chỉ là lệnh mới/STOP/generation đã thay lệnh đang ACK, không phải mất device session.
- Gửi RECEIVED rồi APPLIED bắt buộc tăng thêm một HTTP round-trip cho mỗi lệnh, tăng cửa
  sổ xung đột với Manual refresh250ms. API v1 cho phép final ACK trực tiếp.
- Packet command hợp lệ có thể hết TTL trong đường truyền. Decoder cũ coi trường hợp
  đó là lỗi session/JSON, gây re-auth Manual không cần thiết.

## Thay đổi

Frontend theo dõi Manual intent bằng ref. STOP do D-Pad chỉ phát một lần khi có intent
đang giữ; release/logout/mode switching vẫn dùng STOP tường minh ở service. Auto/disabled
khi không giữ Manual không phát STOP. Giữ nguyên bốn nút, release/blur/unmount safety,
lease10s, renew1.5s và TTL700/3000ms mặc định.

Firmware final ACK APPLIED/REJECTED/FAILED trực tiếp, schema unchanged. Khi write409:
dừng output, chặn controller trong awaiting_command, poll current ngay. Không đổi boot/
session chỉ vì write409. Giữ mode confirmation, fence và deadline đã có để kiểm tra;
không kéo dài deadline từ lỗi/duplicate. Chỉ mở lại controller sau command mới hợp lệ
và APPLIED receipt thành công. KEEPALIVE vẫn phải cùng lease/generation, có mode Auto đã
xác nhận và permit cũ chưa hết; JIT watchdog kiểm tra trước accept. Generation/mode đổi
vẫn hủy intent trước, không cho KEEPALIVE tự tạo handoff mới.

Write409 do session bị thu hồi cũng không cho chạy lại: GET current tiếp theo409 thì
re-auth. GET/session lỗi, transport lỗi, malformed receipt, sensor fault, Auto permit
expiry, heartbeat/poll timeout và driver fault vẫn fail-safe/re-arm như trước. Packet
Manual expired in flight dừng/bỏ command, không re-auth toàn phiên chỉ vì packet đó.

Log mới không chứa secrets: ACK superseded + sequence; HTTP status/RTT cho lỗi ACK;
heartbeat/poll/telemetry failure; Re-auth required kèm reason như sensor_invalid,
sensor_stale, command_poll_timeout, heartbeat_timeout, auto_permit_expired,
auto_authorization_removed, wifi_disconnected hoặc communication_failure.

## Kiểm chứng

- Trước sửa: 3 frontend regression tests mới đều fail (STOP trước MOVE, STOP khi Auto
  làm pad disabled, STOP trùng khi intent đã dừng). Sau sửa tất cả pass.
- Frontend: **112 tests passed**; lint, TypeScript check và production build pass.
- Backend Control/Device/HTTP integration: **86 passed**, 48.87s; bao gồm HTTP Uvicorn thật,
  WebSocket, ordering/TTL và ACK-vs-Stop race trên PostgreSQL test riêng. Không sửa backend
  hoặc ghi dữ liệu/điều khiển xe production để kiểm thử bản vá này.
- Host C codec với ASan/UBSan pass; thêm write409 recovery classification, transport409
  không được coi là response hợp lệ, packet valid nhưng expired-in-flight.
- JSON final ACK/telemetry từ firmware vẫn được Pydantic schemas hiện có chấp nhận.
- Native ESP-IDF `pio run` pass (8.12s, app1023237 bytes, static RAM48532 bytes);
  GPIO9 chân/header4MB checks pass. Chưa flash hay thử xe.
- Một assertion auth-flow cũ được sửa để tìm đúng logout alert khi dashboard polling
  cũng lỗi mạng; không đổi behavior authentication.

## File trong bản vá

```text
frontend/src/hooks/useRobotControl.ts
frontend/src/test/ControlLifecycle.test.tsx
frontend/src/test/RobotControlPage.test.tsx
frontend/src/test/AuthFlow.test.tsx
firmware/src/device.c
firmware/src/protocol.c
firmware/src/protocol.h
firmware/src/robot.c
firmware/src/robot.h
firmware/src/robot_internal.h
firmware/src/safety.c
firmware/test/protocol_test.c
firmware/README.md
docs/phase-6b-report.md
docs/fixes/control-lease-ack-conflict.md
```

Các thay đổi robot serializer/backend tests từ bản sửa500 trước đó vẫn có thể nằm trong
working tree, không thuộc bản vá ACK này. Không đổi GPIO, NVS layout, secrets hoặc schema API.

## Cập nhật và nghiệm thu trên xe

1. Reload frontend mới; nếu chạy production thì build/restart phần phục vụ frontend.
2. Operator ngắt nguồn motor/kê bánh và tự upload firmware từ firmware/:
   `pio run -t upload --upload-port /dev/ttyUSB0`. Không erase flash hoặc nạp lại NVS;
   cấu hình robot_cfg hiện có được giữ. Agent chỉ build, chưa chạy upload.
3. Monitor115200; xác nhận dòng Device session established (6b-2).
4. Acquire, giữ/nhả hướng, chuyển Manual/Auto. Khi vẫn đứng ở trang và kết nối ổn định,
   quyền phải được renew; mode switch không có STOP thừa sau MODE. ACK409 của command đã
   bị thay có thể còn xuất hiện, nhưng không tự tạo session mới chỉ vì409 đó.
5. Thử STOP/mode đồng thời với ACK: output phải dừng, firmware lấy snapshot/fence mới,
   không thực thi lại lệnh cũ. Giữ kiểm tra TTL, mất Wi-Fi, logout và sensor fail-safe.
6. Nếu vẫn tái đăng ký session, lấy dòng Re-auth required/lỗi HTTP ngay trước đó để xác
   định trigger thật. Sensor/timeout thật vẫn có thể làm mất lease theo chính sách an toàn.

Chưa đo latency hoặc xác nhận chuyển động/thời gian giữ lease trên xe thật sau bản vá.
Không bỏ watchdog, tăng TTL để che lỗi hoặc tạo simulator.
