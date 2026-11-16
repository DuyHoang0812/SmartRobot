# Giữ lượt mượn và kiểm tra đường lệnh — firmware 6b-3

Ghi nhận lịch sử 6b-3. Bản hiện tại **6b-4** đã xác nhận relay cấp nguồn motor và thay đổi
khôi phục Auto: [hướng dẫn mới](motor-power-relay-and-auto-recovery.md).

Lượt mượn giữ cho tài khoản đến khi người dùng bấm **Trả xe**. Mất kết nối vẫn dừng
chuyển động; không tự trả xe do timeout, Offline, đổi tab, WebSocket ngắt, logout,
firmware re-handshake hoặc ACK lỗi. Disable user/robot và đổi credential vẫn thu hồi
quyền theo thao tác quản trị.

## Thay đổi

- Migration `0005_persistent_borrow`: `control_sessions.expires_at` cho phép null;
  các lượt mượn đang mở chuyển sang null, lịch sử đã trả giữ nguyên. Trigger logout
  fence lệnh/tăng generation thay vì đóng lượt mượn. Có migration downgrade.
- Backend tách dừng/fence chuyển động khỏi trả xe. TTL lệnh vẫn 700ms Manual và 3000ms
  MODE/Auto permit mặc định. Lệnh quá hạn không được chạy lại.
- Cùng tài khoản acquire lại giữ ID lượt mượn, thay secret và binding đăng nhập,
  reset client_sequence, tăng generation và yêu cầu Manual handoff mới. Credential
  browser cũ bị từ chối. Người khác vẫn không chiếm được xe. Người mượn có thể lấy
  lại credential và trả cả xe đang Offline.
- Renew không gia hạn lượt mượn; giữ Auto permit hoặc gửi lại handoff Manual khi
  firmware vừa kết nối lại. Auto bị hủy không tự resume từ lệnh cache.
- Frontend chỉ release khi bấm **Trả xe**. Blur/tab ẩn/disconnect/unmount/lỗi request
  cố gắng STOP và giữ lượt mượn; lỗi renew được retry. Reload/login tự lấy lại
  lượt mượn của tài khoản; secret vẫn chỉ ở memory, không browser storage/Query cache.
- Firmware 6b-3 đọc `lease_expires_at=null` nhưng vẫn bắt buộc authorization/command
  expiry hữu hạn. Tương thích cả hạn hữu hạn từ backend cũ.
- Serial bổ sung `Poll OK` khi không có lệnh (5 giây/lần), `RX` (tối đa khoảng một
  lần/giây cho MOVE cùng hướng), kết quả ACK handoff/rejection và thay đổi output/PWM.
  Lệnh UART `status` in motors/blind, PWM, sequence/applied/generation, TTL và cảm biến.
- UI đổi “Chuyển động thiết bị” thành “Tín hiệu động cơ”, nêu rõ chưa đo bánh quay.

## Bằng chứng và giới hạn chẩn đoán

Đã đọc database đang chạy bằng transaction **READ ONLY**, không gửi lệnh tới xe.
Trong dữ liệu lịch sử ngày 16/11/2026 (UTC+7), thiết bị báo firmware **6b-2**;
MODE/AUTO sequence 234 và KEEPALIVE 235–239 có ACK **APPLIED**. ESP đã nhận lệnh,
không thể kết luận không nhận lệnh chỉ vì Serial cũ chỉ hiện dòng kết nối.

Có lượt mượn đóng trước `expires_at`; dữ liệu này không đủ phân biệt thao tác người
dùng với blur/WebSocket/lifecycle cũ. Source có các nhánh tự đóng khi mất kết nối,
timeout lệnh, Offline hoặc authenticate boot mới, nay đã sửa.

Cấu hình **file local** bật motors/blind; full/turn=75 và slow=30 trên thang **0–255**
(khoảng 29% / 12%, không phải 75% / 30%). Chưa đọc NVS thực tế trên ESP. PWM thấp,
ENA/ENB chưa enable, nguồn motor/GND hoặc relay nguồn đều cần đối chiếu mạch thật;
chưa có bằng chứng xác định một nguyên nhân phần cứng cụ thể.

Không có encoder: telemetry FORWARD và ACK APPLIED chỉ xác nhận trạng thái phần mềm/
đầu ra driver, không xác nhận điện áp đo thực tế, dòng motor hay tốc độ bánh xe.
Chưa flash, thay NVS hoặc thử chuyển động trên xe thật.

## Cập nhật đồng bộ

Firmware **6b-2 không đọc được authorized envelope có lease expiry null**. Chuẩn bị
build mới rồi cập nhật theo thứ tự; tránh điều khiển trong lúc hai phiên bản chưa đồng bộ:

1. Nạp firmware **6b-3** trước; bản này vẫn hỗ trợ backend cũ. Kê bánh/ngắt nguồn motor
   khi nạp. Từ `firmware/`, chọn đúng cổng thực tế:

   ```bash
   pio run -t upload --upload-port /dev/ttyUSB0
   ```

   Không erase flash, không nạp lại `robot_cfg` để áp dụng thay đổi này.

2. Dừng backend cũ, từ `backend/` chạy migration rồi khởi động lại backend theo cách
   đang triển khai:

   ```bash
   .venv/bin/alembic upgrade head
   ```

3. Cập nhật frontend từ build mới và reload trình duyệt. Serial phải hiện phiên bản
   **6b-3**. Các bước nạp/migration database đang chạy chưa được agent thực hiện.

## Đối chiếu trên xe

1. Mượn xe, giữ/nhả Tiến: có `RX ... direction=FORWARD`, ACK không lỗi và output/duty.
   Nhả dừng; quyền vẫn giữ. Thử bốn hướng trong điều kiện thích hợp. Lùi/quay vẫn có
   giới hạn burst cấu hình; không bỏ giới hạn cảm biến/watchdog.
2. Chuyển Auto: phải có MODE/AUTO ACK APPLIED, sau đó KEEPALIVE định kỳ; không có STOP
   thừa sau MODE. Đường trước trống/hợp lệ mới có output tiến.
3. Nếu chỉ có `Poll OK ... authorized=0`, kiểm tra acquire/renew/MOVE trong Network
   browser: backend hiện không có lệnh hợp lệ để giao. Nếu có RX nhưng REJECTED/FAILED,
   xem flags motors/blind/reset và lỗi ngay trước đó.
4. Nếu RX/ACK/output đều đúng nhưng bánh không quay, gõ `status`, đối chiếu PWM/duty
   với GPIO19/21/5/18 đo thực tế, ENA/ENB, nguồn motor và common GND; kiểm tra relay
   nếu relay thực tế cấp nguồn motor. Không tự suy luận relay là nguồn motor trong code.
5. Rời tab/mất mạng/tải lại/khởi động lại ESP: chuyển động dừng, lượt mượn vẫn thuộc
   tài khoản. Khi kết nối lại phải xác nhận Manual trước lệnh mới. Bấm **Trả xe** mới
   giải phóng cho người khác; thử cả trường hợp xe Offline.

## Kiểm thử

- Backend: PostgreSQL test riêng, REST/WebSocket thật, ordering, ACK/STOP race,
  ownership, login lại, Offline return, reboot, Auto timeout và migration round-trip.
- Frontend: 114 tests đạt; lint, TypeScript và production build đạt.
- Firmware: build ESP-IDF/PlatformIO đạt; codec ASan/UBSan và hợp đồng JSON với
  Pydantic backend đạt; 6 unittest host đạt (provisioning và runtime).
- Runtime host biên dịch các module C controller/manual/auto/safety/motor thật, thay
  API ESP-IDF bằng test doubles. Kiểm tra GPIO/PWM bốn hướng, STOP/resume, blind burst,
  TTL Manual/Auto, ACK handoff, sensor fault và driver failure; không giả lập xe vật lý.
- GPIO/header Flash 4MB kiểm tra đạt. Kết quả trên máy không thay phép đo/kiểm thử xe thật.
