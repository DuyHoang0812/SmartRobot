# Quét, rẽ, lùi tìm lại đường và cân hai bánh — firmware 6b-7

Thuật toán Auto bên dưới là lịch sử 6b-7/6b-8, đã được thay bằng
[6b-9: chọn hướng, lùi một lần rồi quay](auto-commit-backup-turn.md).
Phần chiều motor và cân PWM vẫn áp dụng.

Cập nhật **6b-8**: người dùng thử xe và báo trái/phải của 6b-7 bị ngược. Đã đảo lại
hai hướng pivot dùng chung cho Manual và Auto. Tiến/lùi, trim và thuật toán giữ nguyên.
Bảng dưới đã cập nhật theo 6b-8; nạp 6b-8 thay cho 6b-7.

Người dùng xác nhận: khi Tiến hai bánh cùng chiều nhưng xe lệch phải; OUT1/OUT2 nối
bánh phải, OUT3/OUT4 nối bánh trái. Chiều pivot được chốt theo phản hồi thử xe thực tế
ở 6b-8, thay cho suy luận chiều quay trong 6b-7.

## Chiều motor và cân PWM

| Chuyển động | IN1 | IN2 | IN3 | IN4 |
| --- | --- | --- | --- | --- |
| Tiến | PWM phải | 0 | PWM trái | 0 |
| Lùi | 0 | PWM phải | 0 | PWM trái |
| Trái | 0 | PWM phải | PWM trái | 0 |
| Phải | PWM phải | 0 | 0 | PWM trái |
| Dừng | 0 | 0 | 0 | 0 |

Giữ GPIO19/21/5/18 và PWM 1kHz/8bit. Mỗi bánh có hệ số riêng 50–150%, duty làm tròn
và giới hạn 255. Vì xe lệch phải, đặt mức khởi đầu **trái 90%, phải 100%** để giảm
bánh trái đang chạy nhanh hơn. Base75 cho trái68/phải75. Đây là mức bù ban đầu theo
hướng lệch người dùng báo, chưa phải kết quả cân tốc độ trên xe thật. Không có encoder
nên phần mềm không đo hoặc tự khóa hai tốc độ bằng nhau khi tải/nguồn thay đổi.

Trong Serial Monitor 115200, chọn **Manual**, nhả hết nút và để xe dừng rồi nhập:

```text
status
trim 90 100
```

Thử Tiến ngắn trên mặt phẳng. Nếu vẫn lệch phải, giảm trái từng bước nhỏ, ví dụ
`trim 85 100`; nếu bắt đầu lệch trái thì tăng lại, ví dụ `trim 95 100`. Nếu một bánh
không khởi động được ở PWM thấp, cần chọn lại mức PWM/hệ số theo motor thực tế, không
thể suy ra chính xác chỉ bằng code. `status` hiển thị duty và trim của từng bánh.

Khi đã cân phù hợp, dừng xe ở Manual rồi nhập:

```text
trim save
```

Lưu hai hệ số vào NVS để giữ qua reset; không ghi Wi-Fi/secret. Trim bị từ chối khi
Auto, đang chuyển động hoặc còn intent MOVE. `trim` chưa save chỉ có tác dụng trong
phiên firmware hiện tại.

## Auto theo trình tự mới

1. Phía trước dưới 15cm: dừng PWM, quét **cả trái và phải**.
2. So sánh khoảng trống với `auto_clearance_cm` (mặc định **30cm**, chỉnh theo kích
   thước xe). Chọn bên đủ trống, ưu tiên xa hơn. Mẫu lỗi/không echo là chưa rõ, không
   được coi là đường trống; bên lỗi hết thời gian chờ sẽ tiếp tục quét bên kia.
3. Đưa servo về giữa, chờ mẫu trước mặt hợp lệ; quay đúng phía đã chọn theo thời gian
   cấu hình. Dừng rồi đo mẫu mới phía trước. Thông thì đi tiếp.
4. Hai bên không đủ trống, hoặc đã quay mà trước mặt vẫn bị chắn: lùi ngắn **300ms**,
   dừng ít nhất100ms, quét lại. Khi hai hướng đều dùng được sau một lần quay thất bại,
   ưu tiên hướng khác với hướng vừa thử.
5. Tối đa3 lần lùi trong một đợt phục hồi Auto. Nếu vẫn kẹt thì đứng chờ/quét lại để
   tìm lối, không lùi vô hạn. Chuyển mode mới hoặc đi được vào khoảng trống sẽ bắt đầu
   đợt phục hồi mới. Không có cảm biến sau: lùi là burst hữu hạn, không xác nhận phía
   sau trống. STOP/đổi mode/mất permit/watchdog/lỗi cảm biến vẫn ngắt chuyển động.

Relay vẫn ON theo lượt mượn, kể cả các bước dừng, quét và hãm giữa lùi/quay. Lỗi an toàn
nặng có thể cắt nguồn như trước. Không có gyro/encoder, nên góc quay thực tế cần cân
theo xe; thời gian400ms không khẳng định đúng90°.

Các key tùy chọn trong file cấu hình NVS, có mặc định nếu NVS cũ chưa có:

| Key JSON | Mặc định | Khoảng |
| --- | --- | --- |
| `left_motor_percent` / `right_motor_percent` | 90 / 100 | 50–150 |
| `auto_clearance_cm` | 30 | 15–100cm |
| `auto_backup_ms` | 300 | 50–400ms |
| `auto_turn_left_ms` / `auto_turn_right_ms` | 400 / 400 | 100–1200ms |

## Kiểm thử và áp dụng

8 unittest host đạt. Runtime test biên dịch controller/Auto/motor/output C thật với
ESP-IDF API doubles, kiểm tra:

- Đúng chiều PWM theo OUT1/2 phải, OUT3/4 trái; trim độc lập, clipping255 và chặn trim
  lúc đang chạy; mặc định/kiểu NVS của các key mới.
- Quét hai bên → rẽ → đo lại → tiến; không có đường → lùi → hãm → quét → rẽ hướng mới.
- Quay trái thất bại → lùi → chọn phải; cảm biến một bên lỗi vẫn quét bên còn lại.
- Mỗi burst lùi hữu hạn, chỉ3 burst khi kẹt; STOP và hết permit chặn được lùi.
- Giữ nguồn relay theo lượt mượn và hồi phục lỗi HTTP trong cùng phiên như các bản trước.

Build ESP-IDF/PlatformIO kiểm tra riêng. Test host không đo tốc độ/góc quay hoặc thay
thử nghiệm xe thật. Agent chưa upload, chạy xe hoặc ghi NVS của ESP32 thực tế.

Từ `firmware/`, kê bánh/ngắt nguồn motor lúc nạp, chọn đúng cổng:

```bash
pio run -t upload --upload-port /dev/ttyUSB0
pio device monitor --port /dev/ttyUSB0 --baud 115200
```

Không cần thay backend/frontend hay nạp lại toàn bộ NVS để dùng mặc định 6b-7. Sau nạp,
xác nhận dòng6b-7 và mapping/trim lúc startup; cân Manual trước rồi thử Auto với vùng
trống phía sau cho bước lùi. Dùng `trim save` sau khi đã chọn mức cân phù hợp.
