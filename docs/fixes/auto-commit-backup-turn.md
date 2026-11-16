# Auto chọn lối, lùi một lần rồi quay — firmware 6b-9

Bản mới [6b-10](auto-ver2_6-and-right-drift.md) đối chiếu lại ver2_6, đổi bộ mặc định
sang15cm/400ms và thêm hãm100ms sau quay. Các thông số bên dưới mô tả bản6b-9.

Nhánh cũ lùi xong quay lại quét, bỏ qua việc thực hiện hướng rẽ đã chọn. Nếu vẫn
thấy vật cản, xe có thể tiếp tục lùi; MODE mới còn đặt lại bộ đếm lùi. Bản này giữ
hướng đã chọn qua bước lùi và giới hạn một lượt lùi trong cùng đợt kẹt.

## Trình tự thực hiện

1. Trước mặt dưới15cm: dừng, quét trái rồi phải.
2. Bên đạt `auto_clearance_cm` (mặc định30cm) được coi là lối có thể rẽ. Nếu cả hai
   bên đạt, chọn bên xa hơn; nếu hướng vừa thử thất bại thì ưu tiên bên còn lại.
   Mẫu lỗi/không echo không được coi là khoảng trống.
3. Giữ hướng đã chọn, đưa servo về giữa và chờ mẫu trước hợp lệ. Hãm100ms, lùi
   `auto_backup_ms` (mặc định300ms), hãm100ms rồi quay đúng hướng đã chọn. Không quét
   lại giữa lùi và quay. Thời gian quay mặc định400ms mỗi bên, theo cấu hình hiện có.
4. Dừng quay và lấy mẫu trước mới. Trước mặt đủ15cm thì tiến, dưới40cm dùng tốc độ chậm.
5. Nếu quay xong vẫn bị chắn, đứng chờ rồi quét lại; có thể thử hướng khác nhưng
   không lùi thêm trong cùng đợt kẹt. Cả hai bên không đạt ngưỡng thì đứng quét lại
   sau1s, không lùi khi chưa chọn được hướng.

Một lượt lùi mới chỉ được mở khi xe đã phát output tiến liên tục ít nhất500ms,
với cảm biến trước mới/hợp lệ và khoảng cách >= `auto_clearance_cm`, hoặc khi có
lượt mượn UUID mới. STOP, đổi MODE, đổi generation và khôi phục phiên thiết bị
trong cùng lượt mượn không mở thêm lượt lùi. Trạng thái này nằm trong RAM, không
giữ qua việc khởi động lại MCU/cắt nguồn.

Chiều rẽ giữ đúng bản6b-8; trim trái/phải, relay theo lượt mượn, giới hạn TTL và
watchdog giữ nguyên. Không có cảm biến sau hoặc encoder; thời gian quay chưa đo
được góc thực tế và lùi hữu hạn không xác nhận phía sau trống.

## Kiểm tra đã thực hiện

- 8 unittest host đạt, gồm controller/Auto/motor C thật với ESP-IDF API doubles.
- Kiểm tra quét cả hai bên, giữ hướng đã chọn qua lùi, lùi một lần rồi quay trái/phải;
  đứng khi hai bên kín; hướng quét lỗi không được coi là trống.
- Vẫn bị chắn sau quay, STOP/MODE và re-handshake cùng lượt mượn không sinh thêm
  lùi; mẫu trước trống ngắn100ms không đặt lại bộ đếm; đi thẳng đủ lâu cho phép
  một lượt lùi mới. STOP và permit hết hạn ngắt được bước lùi.
- `pio run` build ESP32 thành công; kiểm tra9 GPIO và kích thước image đạt.

Đây là kiểm tra phần mềm; chưa nạp hoặc thử chuyển động trên xe thật.

## Cập nhật xe

Chỉ cần nạp app6b-9, không cần thay backend/frontend hay nạp lại NVS so với6b-8.
Từ `firmware/`, chọn cổng thực tế của ESP32:

```bash
pio run -t upload --upload-port /dev/ttyUSB0
pio device monitor --port /dev/ttyUSB0 --baud 115200
```

Sau nạp xác nhận log `Device session established (6b-9)`. Khi thử Auto, Serial cần
có thứ tự `selected LEFT/RIGHT` → `preparing one backup` → `BACKUP ... (1/1)` →
`braking before the committed turn` → `Turning committed LEFT/RIGHT` →
`Turn finished` → `resuming DRIVE`, hoặc `rescan without another backup` nếu vẫn bị chắn.
