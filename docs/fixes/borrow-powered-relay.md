# Relay giữ nguồn theo lượt mượn — firmware 6b-5

Thiết kế theo yêu cầu người dùng:

- Mượn xe: bật relay GPIO26 active-low và giữ nguồn cả khi chưa bấm hướng.
- Manual: nút điều khiển thay đổi PWM/chiều motor. Nhả nút/STOP/hết TTL dừng PWM,
  relay vẫn ON. Đứng yên lâu vẫn giữ nguồn khi kết nối còn khỏe và lượt mượn còn mở.
- Auto: thuật toán trên ESP32 điều khiển PWM theo cảm biến trong permit hợp lệ.
  Dừng tránh vật cản, quét servo hoặc đổi Manual/Auto không bật/tắt relay theo từng bước.
- Trả xe/thu hồi quản trị: dừng motor và tắt relay khi ESP nhận snapshot mới.
- Watchdog mất mạng/heartbeat, lỗi driver, Auto fault hoặc reset vẫn có thể cắt nguồn
  an toàn; lượt mượn backend không bị tự trả. Nguồn được khôi phục khi có trạng thái
  lượt mượn hợp lệ sau kết nối lại. `motors_enabled=false` vẫn không bật nguồn motor.

## Thay đổi

Backend thêm `control_session_id` ở cấp ngoài của Device command envelope. Giá trị này
vẫn là UUID lượt mượn khi `command=null`/`control_authorized=false`; null sau khi trả xe.
Tách hai trạng thái để hết TTL chuyển động không bị hiểu thành hết lượt mượn.

Firmware 6b-5 giữ borrow ID riêng với intent/sequence/deadline. Relay dựa trên lượt mượn;
PWM vẫn cần mode được xác nhận, lệnh/Auto permit còn hạn, cảm biến phù hợp và watchdog.
STOP, Manual idle, ACK conflict và đổi generation trong cùng lượt mượn chỉ dừng PWM.
Relay chờ 50ms ổn định khi mới cấp nguồn; giữ liên tục giữa các lệnh.

Envelope UUID lượt mượn phải khớp command. Khi trả xe, firmware xóa borrow ID, vô hiệu
intent và tắt nguồn; command của lượt cũ không được điều khiển lượt mới. UART `status`
hiện `borrowed=1`, `relay=on`, `PWM=0/255` là trạng thái bình thường khi mượn mà đứng yên.

## Kiểm tra

- Host runtime chạy controller/motor/output C thật với ESP-IDF doubles: relay GPIO26
  LOW ngay khi có lượt mượn; không có cạnh OFF qua STOP, đổi mode, Manual TTL và idle.
  Trả xe, lỗi driver hoặc watchdog phải đưa GPIO26 HIGH; command khác borrow ID bị chặn.
- Codec kiểm tra snapshot mượn không có command, trả xe/null, UUID lỗi và UUID không khớp.
- Backend kiểm tra MODE/STOP đã hết TTL vẫn trả borrow ID; release trả null.
- Device task/HTTP retry tests và contract Pydantic vẫn kiểm tra riêng.
- Đây là kiểm thử trên máy; chưa đo điện hoặc chạy bánh trên xe thật.

## Cập nhật

Cập nhật/restart backend trước để có borrow ID trong snapshot idle, sau đó nạp firmware
**6b-5**. Không có migration/NVS layout mới so với 6b-4. Nếu dùng backend cũ, firmware chỉ
suy ra lượt mượn lúc có command và sẽ tắt relay khi idle; cần cập nhật cả hai phía để đạt
hành vi giữ nguồn liên tục.

Từ `firmware/`, kê bánh/ngắt nguồn motor lúc nạp và chọn đúng cổng:

```bash
pio run -t upload --upload-port /dev/ttyUSB0
pio device monitor --port /dev/ttyUSB0 --baud 115200
```

Agent chỉ biên dịch/kiểm thử, chưa upload. Sau cập nhật, mượn và để Manual đứng yên hơn
10 giây: relay vẫn ON, PWM=0. Giữ/nhả hướng và đổi Auto/Manual: relay không nhả giữa các
lệnh. Bấm Trả xe: relay OFF sau lần polling xác nhận; không cần nạp lại `robot_cfg`.
