# Auto ver2_6 tích hợp với web — 6b-14

Cập nhật6b-15: servo đặt thẳng góc đích như file mẫu, bỏ quét chậm2°/20ms;
chờ ổn định600ms trước đọc cảm biến. Các hành vi Auto/web khác giữ nguyên.

Đã chuyển logic loop/performRecoveryManeuver/backUpAndTurn trong
firmware/ver2_6_esp32.ino sang firmware ESP-IDF đang phục vụ web.
Không mở Wi-Fi AP/WebServer điều khiển relay riêng như file mẫu.

- >=40cm tiến thường;15–<40cm tiến chậm, còi ngắt quãng; dưới15cm dừng/quét.
- Quét trái trước, chờ ổn định600ms và mẫu hợp lệ. Trái>=15cm thì chọn trái ngay,
  không so sánh để chọn bên xa hơn. Chỉ quét phải nếu trái bị chắn hoặc chưa rõ.
- Phải>=15cm thì chọn phải. Hai bên kín thì về giữa, chờ rồi kiểm tra lại như mẫu.
  Bỏ các nhánh bổ sung lùi800ms, quay thoát gấp đôi và giới hạn một lượt lùi của bản trước.
- Có hướng: lùi400ms, dừng100ms, quay hướng chọn400ms, dừng100ms. NVS tùy chỉnh
  thời gian vẫn được giữ. Khoảng cách thay đổi không quá5cm trong3 giây ở DRIVE thì
  thử lùi/quay trái như nhánh STUCK của mẫu. Không có encoder nên không xác nhận kẹt cơ khí.

Các điều chỉnh để dùng với web:

- Chỉ kích hoạt Auto sau lệnh chọn Auto được backend xác nhận và permit còn hạn.
  State machine thay cho waitMs/delay để Manual/STOP/Trả xe/mất permit ngắt ngay được.
- Relay GPIO26 giữ theo lượt mượn, không cần nút relay/AP riêng. Mượn xe không tự chạy Auto.
- Giữ servo chậm2°/20ms theo yêu cầu trước; sau ổn định lấy mẫu hợp lệ, không dùng bộ3 mẫu nữa.
  Đưa cảm biến về giữa trước lùi/quay để kiểm tra sensor/watchdog theo giao thức hiện tại,
  thay vì để cảm biến nhìn bên suốt thao tác như code mẫu. Chờ giữa tối thiểu200ms và
  vẫn phải thỏa điều kiện servo ổn định/cảm biến mới.
- No-echo/giá trị lỗi không được đổi thành999cm đường trống như mẫu. Lỗi sensor vẫn dừng.
- Giữ trim trái100%/phải83,5%, GPIO và chiều motor. Không thay API backend/frontend.

9 unittest host đạt: ưu tiên trái dù phải xa hơn, xét phải khi trái kín, hai bên kín/unknown
không tự bịa đường trống, đúng400/100/400/100ms, STUCK3 giây, chuyển Manual giữa pivot,
permit hết hạn và retry HTTP. Build ESP32 thành công; chưa nạp hoặc thử xe thật.

Từ firmware/, nạp app bằng cổng thực tế:

```bash
pio run -t upload --upload-port /dev/ttyUSB0
```

Không cần xóa NVS. Sau nạp log kết nối cần có6b-14; các log Auto mới mang tiền tố ver2_6.
