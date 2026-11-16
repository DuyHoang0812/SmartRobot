# Auto theo ver2_6 và cân xe lệch phải — firmware 6b-10

Đã đối chiếu trực tiếp `performRecoveryManeuver()`, `backUpAndTurn()` và bảng PWM
trong [ver2_6_esp32.ino](../../firmware/ver2_6_esp32.ino). Bản tham chiếu dùng ngưỡng
15cm, lùi400ms, hãm100ms, quay400ms và hãm100ms sau quay. Bộ mặc định 30cm/300ms
trước đây khác bản tham chiếu, có thể bỏ qua lối bản cũ chấp nhận.

## Auto hiện tại

Trước mặt dưới15cm thì dừng, quét trái0° và phải180° với thời gian ổn định600ms.
Chọn bên đạt ít nhất15cm, ưu tiên bên xa hơn hoặc bên khác với hướng vừa thử thất bại.
Đưa servo về90°, chờ mẫu trước hợp lệ và hãm100ms, lùi400ms, hãm100ms, quay400ms
về phía đã chọn, hãm100ms rồi lấy mẫu trước mới. Thông thì tiến; 15–<40cm đi chậm,
>=40cm đi với tốc độ thường. Thông số thời gian vẫn có thể tùy chỉnh bằng NVS.

Giữ yêu cầu quét cả hai bên từ các bản trước; ver2_6 chỉ quét phải nếu trái bị chắn.
Hai bên kín thì đứng quét lại. Quay xong vẫn bị chắn thì thử hướng khác, không được
lùi thêm cho tới khi đã phát output tiến liên tục500ms ở khoảng trống đạt ngưỡng,
hoặc bắt đầu lượt mượn mới. MODE/khôi phục phiên thiết bị không mở thêm lượt lùi.

Không chuyển no-echo thành999cm trống hoặc kết luận xe kẹt chỉ từ khoảng cách không
đổi trong3 giây như bản tham chiếu. Cảm biến lỗi vẫn chặn chuyển động. Các bước dùng
state machine, không chặn xử lý STOP, permit hoặc watchdog bằng delay dài.

## Bù hai bánh

Theo dây người dùng xác nhận: OUT1/2 là bánh phải, OUT3/4 là bánh trái. Vì xe vẫn
lệch phải khi Tiến cùng chiều, giảm tiếp hệ số bánh trái từ90% xuống **85%**, giữ phải
**100%**. Base75 tạo duty trái64/phải75; base30 tạo trái26/phải30. Áp dụng cho cả
Manual và Auto; giữ chiều Tiến/Lùi/Trái/Phải đã xác nhận ở6b-8.

Đây là bước cân tiếp theo dựa trên hướng lệch, chưa phải đo tốc độ bánh. Không có
encoder nên phần mềm không tự biết xe đã đi thẳng hay chưa. Nếu vẫn lệch phải khi
thử trên mặt phẳng, cần giảm trái từng5 điểm và thử lại; nếu lệch trái thì tăng lại.
Chọn Manual và nhả nút trước khi chỉnh, ví dụ:

```text
trim 80 100
trim save
```

## Nạp app và cấu hình đã lưu

Nạp **6b-10** như các bản trước; không cần thay backend/frontend hoặc xóa NVS:

```bash
cd firmware
pio run -t upload --upload-port /dev/ttyUSB0
```

Đổi cổng theo ESP32 thực tế. Agent chỉ build và kiểm thử, chưa upload hoặc chạy xe.
Log kết nối sau nạp cần có `Device session established (6b-10)`.

Nạp app giữ nguyên NVS, nên bản này nhận diện và chuyển bộ mặc định cũ khi đọc:

| Bộ cũ chưa có revision mới | Bộ hoạt động trong6b-10 |
| --- | --- |
| Trim trái90 / phải100 | Trái85 / phải100 |
| Auto30cm / lùi300ms / quay trái400ms / phải400ms | 15cm / 400ms / 400ms / 400ms |

Chỉ nhận diện đúng bộ cũ; các bộ tùy chỉnh khác được giữ. NVS thiếu key dùng mặc định
mới. Việc đọc không ghi lại flash/credential. Tool provisioning mới và lệnh save ghi
revision để người dùng vẫn có thể chủ động chọn lại giá trị cũ mà không bị đổi sau reset.

Nếu đã dùng bộ Auto tùy chỉnh nhưng muốn chuyển sang bộ ver2_6, chọn Manual, nhả nút,
mở Serial Monitor115200 và nhập:

```text
auto reference
auto save
status
```

`auto reference` áp dụng ngay; `auto save` lưu bốn thông số Auto. `status` hiển thị
thông số thực tế đang dùng. Hai lệnh này không ghi lại Wi-Fi/secret hoặc trim bánh.

## Kiểm tra

9 unittest host đạt. Các bài mới kiểm tra loader/saver NVS C thật với API doubles:
chuyển bộ cũ, giữ bộ tùy chỉnh, lưu revision, không ghi flash khi đọc, báo lỗi khi
ghi thất bại. Runtime kiểm tra lối15cm được chọn, đã quét cả hai bên, lùi400ms,
hãm100ms, quay400ms, hãm100ms trước tiến; trim85/100 vào đúng kênh trái ở cả Manual
và Auto. Các hồi quy về lùi lặp, STOP, permit hết hạn và lỗi HTTP vẫn được chạy.

`pio run`, kiểm tra GPIO/image và kiểm tra định dạng/lint cũng được chạy. Kiểm thử host
không đo góc quay, vận tốc hoặc độ thẳng trên xe thật.
