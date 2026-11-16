# Auto lùi xong quay ngay — firmware 6b-12

Bản [6b-13](auto-slow-scan-side-turn.md) bỏ nhánh quay thoát800ms bên dưới; hai bên kín
thì lùi lâu hơn rồi quét lại. Servo quét chậm và lấy đủ dữ liệu trước khi chọn hướng.

Trim theo yêu cầu mới: **trái100%, phải82%**. Base75 tạo duty trái75/phải62.
Các preset NVS cũ được chuyển khi đọc, gồm bộ100/80 của6b-11; không cần xóa NVS.
GPIO/chiều quay giữ nguyên như file tham chiếu: trái GPIO5/18, phải GPIO19/21.

Manual và Auto được gọi riêng theo mode. Code không cho thấy Manual đang được gọi
trong Auto; tuy nhiên bản trước có khoảng chờ100ms, chờ mẫu cảm biến mới và nhánh
quét lại sau lùi. 6b-12 bỏ các bước chờ này giữa lùi và quay, và chỉ dùng sequence
inhibition của Manual cho Manual. Ngưỡng dừng tiến15cm vẫn bảo vệ output tiến;
không chặn output lùi hoặc pivot chỉ vì phía trước còn gần vật cản.

## Trình tự

1. Trước mặt dưới15cm: dừng, quét cả hai bên.
2. Có bên đạt ngưỡng: chọn hướng đó. Cả hai đều đạt thì ưu tiên xa hơn hoặc bên khác
   với hướng vừa thử thất bại. Nếu cả hai không đủ trống nhưng có mẫu đo hợp lệ,
   chọn bên có khoảng đo lớn hơn để thực hiện quay thoát sau lùi.
3. Về giữa, chờ mẫu trước hợp lệ và hãm100ms. Lùi theo thời gian cấu hình (mặc định400ms).
4. Hết thời gian lùi: trả output quay ngay trong cùng control tick. Không quét lại,
   không yêu cầu mẫu trước mới hơn hoặc khoảng cách trước phải trên15cm. Motor
   driver zero các input trước đổi cực như các chuyển hướng khác.
5. Có lối thì quay theo thời gian cấu hình (mặc định400ms). Quay thoát khi các mẫu bên
   đều dưới ngưỡng dùng gấp đôi thời gian bên đã chọn (mặc định800ms). Không có encoder/
   gyro nên800ms không xác nhận xe đã quay đúng180° trên thực tế.
6. Dừng100ms sau quay, lấy mẫu trước mới rồi tiến nếu thông. Vẫn bị chắn thì đứng
   quét lại. Giữ tối đa một lượt lùi/đợt kẹt để tránh lùi liên tục.

Khi cả hai bên đều không có mẫu đo hợp lệ, xe đứng quét và chưa bắt đầu lùi vì chưa
chốt được hướng quay. Không coi no-echo là đường trống. STOP, permit/watchdog và lỗi
cảm biến vẫn ngắt chuyển động; không bỏ kiểm tra độ mới/hợp lệ của cảm biến.

## Kiểm tra và cập nhật

9 unittest host đạt. Runtime C với API doubles kiểm tra: Manual bị chặn ở8cm rồi
chuyển sang Auto vẫn lùi/quay được; lùi400ms không bị giới hạn burst Manual300ms;
đúng tick hết lùi chuyển sang quay với mẫu8cm còn trong cache, không STOP gap/quét
giữa hai bước; giữ hướng đã chốt; quay thoát800ms; permit hết hạn/lỗi sensor vẫn
dừng được pivot. Các hồi quy lùi lặp, MODE/reconnect và HTTP retry vẫn đạt.

Build ESP32, lint và kiểm tra GPIO/image đạt. Chưa nạp hoặc thử chuyển động xe thật.
Từ `firmware/`, chọn cổng thực tế của ESP32 và nạp:

```bash
pio run -t upload --upload-port /dev/ttyUSB0
```

Sau nạp log cần có `Device session established (6b-12)`. Khi tránh vật cản, kiểm tra
thứ tự `BACKUP ... (1/1)` → `Backup finished; turning immediately toward committed direction`
→ `Turning committed LEFT/RIGHT`. Nhánh quay thoát có hậu tố `(escape turn)`.
