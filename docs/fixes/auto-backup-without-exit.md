# Auto lùi khi chưa tìm được lối — 6b-11

Trình tự bên dưới mô tả6b-11. Bản [6b-12](auto-immediate-turn.md) thay bước quét sau
lùi bằng hướng quay đã chốt trước lùi, chuyển ngay sang quay khi hết thời gian lùi.

Nhánh cũ chỉ chuẩn bị lùi nếu đã quét thấy ít nhất một bên đủ `auto_clearance_cm`.
Khi hai bên bị chắn hoặc cả hai mẫu quét chưa đo được, xe chuyển sang WAIT mà không
lùi. 6b-11 sửa nhánh này để tạo khoảng lùi trước khi tìm đường lại.

- Có lối ngay: giữ hướng đã chọn → lùi hữu hạn → hãm100ms → quay → hãm100ms → đo lại.
- Chưa có lối: về giữa, chờ mẫu trước hợp lệ → lùi hữu hạn → hãm100ms → quét lại cả
  hai phía. Lúc này tìm được bên đủ trống thì quay về bên đó, không lùi thêm.
- Chưa có lối sau lượt lùi: đứng quét lại. Không biến mẫu lỗi/no-echo thành hướng trống.

Mặc định lùi400ms, quay400ms. Giữ tối đa một lượt lùi trong cùng đợt kẹt; chỉ mở lại
sau khi phát output tiến liên tục500ms ở khoảng trống đạt ngưỡng hoặc có lượt mượn mới.
MODE/khôi phục phiên thiết bị không đặt lại giới hạn này. STOP, mất permit và lỗi cảm
biến vẫn dừng được bước lùi. Trạng thái bộ đếm trong RAM không giữ qua reset MCU.

Trim hiện tại theo yêu cầu: **trái100%, phải80%**. Base75 tạo duty trái75/phải60.
GPIO/mapping/chiều quay không đổi: trái IN3/4 GPIO5/18, phải IN1/2 GPIO19/21.
Các bộ preset NVS cũ85/100,90/100,105/100 hoặc100/85 được nhận diện và chuyển sang
100/80 khi đọc, không cần xóa/cấp lại NVS. Các bộ tùy chỉnh khác và giá trị lưu bằng
revision mới được giữ. Không ghi flash khi đọc cấu hình.

9 unittest host đạt, gồm các hồi quy C thật với API doubles: cả hai bên bị chắn hoặc
chưa đo được vẫn có một lần lùi; sau đó không có output quay khi chưa biết lối và
không có lần lùi thứ hai. Khi xuất hiện lối trái/phải thì quay theo lối đó. Các kiểm
tra lùi/quay hữu hạn, STOP/permit, MODE/reconnect, trim và retry HTTP vẫn đạt.
Build ESP32 và kiểm tra GPIO/image được chạy riêng; chưa thử chuyển động trên xe thật.

Nạp app từ `firmware/`, đổi cổng theo ESP32 thực tế:

```bash
pio run -t upload --upload-port /dev/ttyUSB0
```

Agent chỉ build/kiểm thử, chưa chạy lệnh nạp. Sau nạp, log cần có phiên bản `6b-11`.
Nhánh mới có log `Neither side is clear; backing up once then rescanning for an exit`,
tiếp theo là `BACKUP ... (1/1)`, `braking before rescanning` và `Searching for a path`.
Nếu thấy `backup already used`, xe đang giữ giới hạn một lần lùi trong cùng đợt kẹt.
