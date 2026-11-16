# Auto tiếp tục xử lý sau khi quét vật cản — firmware 6b-6

Lịch sử 6b-6. Bản **6b-7** bổ sung lùi tìm lại đường, sửa chiều quay theo dây motor
thực tế và bù PWM mỗi bánh: [hướng dẫn hiện tại](auto-backup-and-wheel-trim.md).

Người dùng xác nhận servo quét hai bên rồi xe đứng yên và kêu còi. Source có hai
đường vào HALT cố định: hai bên đều dưới 40cm, hoặc sau khi quay vẫn thấy vật cản.
HALT không kiểm tra lại nên bỏ vật cản ra cũng không tiếp tục nếu không đổi mode.

## Sửa thuật toán

- Phân biệt ngưỡng dừng **15cm** với ngưỡng giảm tốc **40cm**. Khi quét, hướng có
  khoảng cách hợp lệ từ 15cm được xem xét; chọn bên xa hơn. Không yêu cầu cả lối
  tránh phải đạt 40cm. Ngưỡng 40cm vẫn quyết định tốc độ tiến thường/chậm.
- Sau quét: về giữa, đợi servo ổn định và mẫu trước mặt hợp lệ, quay phía đã chọn
  tối đa 400ms. Dừng quay rồi bắt buộc đo mẫu trước mặt mới trước khi tiến tiếp.
- Nếu hai bên đều bị chắn hoặc quay xong trước mặt vẫn bị chắn: vào `AUTO_WAIT`,
  dừng PWM và tiếp tục kiểm tra. Đường trước thông thì tiếp tục DRIVE; nếu còn
  chắn thì quét lại sau mốc 1 giây, khi có mẫu trước mặt hợp lệ.
- `AUTO_HALT` dành cho intent/quyền đã vô hiệu hóa, không được tự chạy lại từ cache.
  WAIT chỉ hoạt động trong Auto đã xác nhận, permit còn hạn và watchdog/cảm biến hợp lệ.
- Giữ relay theo lượt mượn của 6b-5: đứng chờ, quét hoặc quay không ngắt nguồn relay.

Serial bổ sung các bước `scanning LEFT`, `LEFT ...; scanning RIGHT`, `selected LEFT/RIGHT`,
`Turning ... for 400ms`, `Turn finished`, `Waiting for space`, `resuming DRIVE` cùng
khoảng cách thực tế. Nếu cả hai bên dưới 15cm, đứng yên/phát còi và quét lại là hành vi
đúng; firmware không tự coi dữ liệu cảm biến lỗi là đường trống.

## Kiểm thử

Regression mới tái hiện lỗi trước bản sửa. Sau sửa, runtime C với ESP-IDF API doubles
kiểm tra:

1. Trước 8cm, trái 25cm, phải 20cm: chọn/quay trái; sau quay trước mặt thông thì tiến.
2. Hai bên bị chắn rồi vật cản phía trước được bỏ đi: tự tiếp tục mà không đổi mode.
3. Đứng chờ rồi phía phải thông: quét lại và quay phải.
4. Quay xong vẫn bị chắn: tiếp tục quét, không khóa vĩnh viễn ở HALT.

Các bước thử chạy qua thời gian servo settle và nhiều KEEPALIVE mới; relay vẫn ON,
mode/permit/watchdog vẫn được kiểm tra. 7 unittest host đạt, bao gồm các luồng Manual,
relay, TTL, lỗi sensor/driver và retry HTTP trước đó. Build ESP-IDF kiểm tra riêng.
Đây không phải phép đo chuyển động hoặc nghiệm thu trên xe thật.

## Cập nhật

Bản này chỉ đổi firmware, không cần migration, sửa backend/frontend hoặc nạp lại NVS
so với 6b-5. Kê bánh/ngắt nguồn motor khi nạp, từ `firmware/` chọn đúng cổng ESP:

```bash
pio run -t upload --upload-port /dev/ttyUSB0
pio device monitor --port /dev/ttyUSB0 --baud 115200
```

Xác nhận dòng **6b-6**, sau đó thử Auto với khoảng trống bên trái/phải. Log phải cho thấy
khoảng cách hai bên, hướng được chọn và bước đo lại sau quay. Agent chưa upload hay thử
trên xe thật. Nếu vẫn đứng, log khoảng cách và phase mới giúp phân biệt không có đường
an toàn với lỗi motor/servo hoặc cảm biến.
