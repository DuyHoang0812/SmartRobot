# Relay cấp nguồn motor và khôi phục Auto — firmware 6b-4

Ghi nhận lịch sử: **6b-5** thay relay theo chuyển động bằng relay giữ nguồn cả lượt mượn,
theo yêu cầu người dùng. Xem [hướng dẫn hiện tại](borrow-powered-relay.md).

Người dùng xác nhận GPIO26/relay cấp nguồn motor: bản `ver2_6_esp32.ino` phải bấm
**BẬT RELAY** trước khi chạy. Firmware trước đây giữ relay OFF khi điều khiển, khiến
IN1–IN4 có thể báo FORWARD trong lúc L298N/motor không có nguồn. Đây là lỗi điều khiển
nguồn được xác định từ source và thông tin đấu dây, chưa phải kết quả đo điện trên xe.

## Đối chiếu với ver2_6

| Phần | Bản tham chiếu | Bản 6b-4 |
| --- | --- | --- |
| IN1/IN2/IN3/IN4 | GPIO19/21/5/18 | Giữ nguyên |
| Tiến/lùi/trái/phải | PWM/0/PWM/0; 0/PWM/0/PWM; 0/PWM/PWM/0; PWM/0/0/PWM | Giữ nguyên |
| PWM | 1kHz, 8 bit, full/slow/turn=75/30/75 | Giữ nguyên, đọc tốc độ NVS đã cấu hình |
| Relay | GPIO26 active-low, có nút bật riêng | Bật trước chuyển động hợp lệ, chờ 50ms rồi PWM; dừng/lỗi tắt |
| Auto khoảng cách | 15cm dừng, 40cm giảm tốc | Giữ ngưỡng; cảm biến lỗi vẫn dừng |
| Mạng | ESP phát AP/web relay, Auto chạy local | Backend cấp lệnh/permit hữu hạn, retry lỗi ngắn trong cùng phiên |

Không thay GPIO, partition hoặc cấu trúc NVS. Key `relay_console` cũ vẫn đọc được;
nguồn motor do controller quản lý. UART `relay off` hủy intent hiện tại; on/toggle bị
từ chối để tránh nguồn motor được bật ngoài luồng lệnh đã kiểm tra.

## Vì sao Auto tự về Manual

Log người dùng có nhiều `HTTP -1, transport=0`, ACK RTT 260–264ms, trong khi timeout
cũ 250ms. Mỗi lỗi telemetry/heartbeat/poll/ACK đều gọi reset toàn phiên; authenticate
boot mới đặt requested mode về Manual. Frontend còn phát STOP khi blur/tab ẩn dù đang
Auto; STOP chuyển về Manual. Mở Serial Monitor có thể kích hoạt nhánh blur này.

Bản sửa:

- Timeout socket hiệu dụng tối thiểu 400ms. TTL lệnh vẫn 700/3000ms và watchdog độc lập.
- Lỗi transport/408/429/5xx retry trong phiên hiện tại. Watchdog vẫn dừng/tái handshake
  nếu mất giao lệnh/heartbeat thực sự, không gia hạn deadline từ lỗi hoặc duplicate.
- Heartbeat retry giữ counter cũ; chờ heartbeat đầu tiên hợp lệ trước nhận lệnh.
- ACK lỗi mạng được lưu để retry đúng body, không `robot_accept` lại cùng sequence.
  Handoff có ACK receipt bị mất chỉ được xác nhận bằng MOVE/KEEPALIVE mới đã được
  backend cho phép, cùng lease/generation/mode, trong hạn handoff gốc. Không chạy cache.
- ACK APPLIED mới, không duplicate, cũng chứng minh giao lệnh còn kết nối; nó không
  kéo dài TTL command. Telemetry không có quyền làm mới watchdog điều khiển.
- Telemetry tối đa khoảng 2Hz, khoảng 1Hz lúc luồng MOVE liên tục bận; ưu tiên poll/ACK
  và heartbeat. Lỗi telemetry backoff 0.5–2s, giữ nguyên body/counter để retry idempotent.
  Telemetry409 bỏ mẫu cũ và poll lại, không dừng motor chỉ vì mẫu quan sát tới trễ.
- Backend ghi nhận ACK MOVE tới trễ khi chỉ bị refresh cùng hướng, cùng lease/generation,
  còn TTL, mode đã xác nhận. Lệnh cũ vẫn SUPERSEDED, head không thay đổi. STOP/đổi hướng/
  đổi generation/expiry tiếp tục chặn ACK cũ chưa từng ghi nhận.
- Blur/tab ẩn dừng Manual intent đang giữ; không phát STOP cho Auto/idle. MODE tự fence
  chuyển động cũ; service không phát STOP vô điều kiện trước MODE.
- Khi cần handshake mới, backend giữ requested mode của người mượn. Fresh renew yêu
  cầu safe MODE handoff rồi mới chạy tiếp. UI vẫn chọn Auto; quyền mượn giữ đến Trả xe.

## Kiểm thử

- Backend Control/Device/HTTP/WebSocket trên PostgreSQL test riêng: **91 passed**.
  Bao gồm giữ Auto sau timeout/reboot, ACK refresh cùng hướng và từ chối đổi hướng/STOP.
- Frontend: **116 passed**; kiểm tra Auto không bị STOP bởi blur/tab ẩn/renew lỗi,
  Manual vẫn dừng khi nhả/blur và queued MOVE bị bỏ trước MODE.
- Host C chạy controller/motor/output thật với API ESP-IDF doubles: GPIO26 HIGH khi
  khởi động, LOW trước PWM, chờ 50ms; STOP/watchdog/sensor/driver fault cắt nguồn.
- Host test chạy `device_task`, protocol, controller và output C thật với HTTP doubles:
  heartbeat/poll/ACK/telemetry có RTT 260ms; mất hai MODE ACK receipt, nhiều lỗi transport,
  retry body/counter giữ nguyên; cuối test chỉ có một phiên, Auto/FORWARD và relay ON.
- Codec ASan/UBSan và JSON serializer/Pydantic contract được kiểm tra riêng.
- Các test host không đo điện áp, dòng motor, độ trễ thật hoặc bánh xe trên phần cứng.

## Áp dụng và nghiệm thu

1. Khởi động lại backend từ source mới; cập nhật/reload frontend mới. Nếu đã chạy
   migration `0005_persistent_borrow` thì bản sửa này không cần migration mới.
2. Kê bánh/ngắt nguồn motor khi nạp; từ `firmware/` chọn đúng cổng ESP32:

   ```bash
   pio run -t upload --upload-port /dev/ttyUSB0
   pio device monitor --port /dev/ttyUSB0 --baud 115200
   ```

   Nạp app thường giữ NVS; không erase flash hoặc nạp lại `robot_cfg` cho bản sửa này.
   Agent chỉ build, chưa chạy upload, điều khiển xe hoặc sửa database đang chạy.
3. Cấp lại nguồn motor, mượn xe, giữ Tiến ở khoảng trống. Log mong đợi:
   `Device session established (6b-4)`, RX/FORWARD, `Motor power relay ON`, sau 50ms
   `Output direction=1 duty=.../255`. Nhả nút phải dừng và relay OFF.
4. Chọn Auto: safe ACK thành công rồi relay ON/PWM; chuyển sang Serial Monitor không
   tự gửi STOP/đổi Manual. Lỗi telemetry đơn lẻ phải ghi deferred, không tạo boot mới.
5. Gõ `status` nếu vẫn đứng: đối chiếu `relay=on`, PWM, sensor_valid/settling, seq/applied
   và TTL; kiểm tra điện áp nguồn motor/ENA/ENB/common GND nếu đã có relay ON/PWM đúng.
   Thiết bị chưa có encoder nên FORWARD vẫn là tín hiệu driver, không đo chuyển động.
