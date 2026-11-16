# Quét chậm, đủ dữ liệu rồi rẽ — firmware 6b-13

## Các thay đổi

- Trim **trái100%, phải83,5%**. Hệ số hỗ trợ một chữ số thập phân cả trong JSON, UART,
  trạng thái runtime và NVS. Base75 tạo duty trái75/phải63 trên thang255; không cắt83,5
  xuống83. GPIO/chiều quay giữ nguyên: trái5/18, phải19/21.
- Servo di chuyển từng bước **2° mỗi20ms**, thay cho nhảy trực tiếp đến0°/180°. Tốc độ
  mục tiêu khoảng90°/0,9s. Đây là nhịp lệnh phần mềm, chưa đo chuyển động servo thật.
- Đến trái0° thì đứng nguyên, ổn định600ms rồi lấy **3 mẫu mới độc lập**, dùng trung vị.
  Đủ dữ liệu trái mới bắt đầu sang phải180°, dừng và lấy3 mẫu tương tự. Không tính lại
  một mẫu cache thành nhiều mẫu. Timeout lấy mẫu bắt đầu sau khi servo đến nơi và
  ổn định;800ms chưa đủ dữ liệu thì hướng đó là chưa rõ.
- Bỏ khoảng WAIT1s nhìn thẳng giữa các lần quét. Khi chưa tìm được lối hoặc sau một
  lần rẽ vẫn bị chắn, tiếp tục quét trái/phải. Các khoảng đứng lấy dữ liệu, chờ servo
  ổn định và hãm100ms vẫn cần thiết và có log tương ứng.
- Bỏ nhánh `escape_turn` nhân đôi thời gian quay ở6b-12. Chỉ rẽ trái/phải về bên đã đo
  đủ `auto_clearance_cm`, dùng thời gian cấu hình bên đó (mặc định400ms), rồi đo lại trước.
  Không có encoder/gyro nên góc rẽ thực tế vẫn phụ thuộc xe, không xác nhận đúng90°.
- **Hai bên đều đo thấy kín:** về giữa, lùi gấp đôi `auto_backup_ms`, tối đa800ms
  (mặc định800ms), rồi quét lại từ vị trí mới. Không tự quay vào bên đang bị chắn.
  Khi tìm được lối sau lượt lùi này, về giữa rồi rẽ bình thường, không lùi thêm.
- Nếu đã có lối ngay, vẫn lùi mặc định400ms rồi chuyển ngay sang rẽ theo hướng đã chọn.
  Giữ tối đa một đợt lùi trong cùng lần kẹt; chưa có lối thì tiếp tục quét. Điều kiện
  đi thẳng đủ500ms hoặc lượt mượn mới để mở lại lượt lùi, các watchdog và STOP giữ nguyên.

800ms là thời gian lùi để thử tạo thêm khoảng trống, chưa phải quãng đường đo được.
Xe không có encoder hoặc cảm biến sau; cần thử thực tế để cân thời gian theo không gian xe.

## Cấu hình và cập nhật

Nạp app6b-13, không cần thay backend/frontend hoặc xóa NVS. Khi đọc NVS cũ, các bộ
preset đã dùng trong những bản trước (gồm100/82 của6b-12) chuyển sang100/83,5. Bộ tùy
chỉnh khác được giữ. NVS cũ `left_pct/right_pct` vẫn đọc được; `trim save` và provisioning
mới dùng u32 `left_pct10/right_pct10` để lưu độ chính xác0,1%, kèm revision16. Đọc cấu
hình không ghi flash hoặc credential.

Nếu cần chỉnh bằng Serial, chọn Manual, nhả hết nút, rồi nhập:

```text
trim 100 83.5
trim save
status
```

UART cũng nhận dấu phẩy `83,5`. JSON dùng dấu chấm83.5. Lệnh save lưu qua reset.
Không tự thay các thời gian quay đã tùy chỉnh trong NVS; nếu muốn bộ mặc định400ms
hai bên, chọn Manual rồi dùng `auto reference`, `auto save`.

Từ `firmware/`, chọn cổng ESP32 thực tế và nạp:

```bash
pio run -t upload --upload-port /dev/ttyUSB0
```

Agent chỉ build/kiểm thử, chưa nạp hoặc chạy xe. Sau nạp xác nhận log kết nối `6b-13`.
Log Auto cần có `sweeping LEFT slowly`, `LEFT reached; holding for 3 fresh sensor samples`,
`LEFT data ready`, rồi mới `sweeping RIGHT slowly`. Hai bên kín có `BACKUP 800ms ... next=SCAN`;
có lối thì `Selected LEFT/RIGHT` và `Turning selected ... for 400ms` với cấu hình mặc định.

## Kiểm tra

9 unittest host đạt. Các hồi quy mới biên dịch C thực với API doubles kiểm tra giới hạn
2°/20ms cho mọi bước servo; giữ trái/phải chờ đủ3 mẫu riêng biệt, không tính lại cache;
lùi800ms khi hai bên kín rồi quét lại, không quay khi chưa có lối; rẽ400ms không bị nhân
đôi; trim83,5% đúng kênh và lưu/đọc lại835 từ NVS. Các kiểm tra STOP, hết permit, lỗi
cảm biến, MODE/reconnect, giới hạn lượt lùi và retry HTTP vẫn đạt.

Build ESP32, lint/định dạng, GPIO/image và kiểm tra codec/hợp đồng JSON với schema
backend được chạy riêng. Các kiểm tra phần mềm không thay việc thử góc rẽ, tốc độ
servo hoặc quãng lùi trên xe thật.
