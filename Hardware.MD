# MÔ TẢ CÁC LINH KIỆN, SƠ ĐỒ KẾT NỐI VÀ NGUYÊN LÝ HOẠT ĐỘNG CỦA XE ROBOT THÔNG MINH

## 1. Tổng quan về hệ thống

Hệ thống xe robot thông minh (SmartRobot) được thiết kế sử dụng vi điều khiển ESP32 làm bộ xử lý trung tâm, kết hợp với các linh kiện như module điều khiển động cơ L298N, cảm biến siêu âm HC-SR04, động cơ servo SG90, module relay, buzzer và các động cơ điện một chiều. Hệ thống có mục tiêu hỗ trợ hai chế độ vận hành chính: điều khiển thủ công thông qua giao diện điều khiển và tự động phát hiện, tránh vật cản.

Về cấu trúc phần cứng, hệ thống được chia thành hai tầng. Tầng trên bố trí ESP32, bộ pin cung cấp năng lượng và các đầu nối tín hiệu. Tầng dưới bố trí mạch giảm áp DC-DC, bộ điều khiển động cơ, hai động cơ DC, cảm biến siêu âm, động cơ servo, module relay, buzzer, LED báo nguồn và các đầu nối phụ trợ.

Các tầng được liên kết với nhau bằng hệ thống dây dẫn và connector, bảo đảm tín hiệu điều khiển từ ESP32 có thể truyền đến các thiết bị ở tầng dưới.

Dựa trên sơ đồ nguyên lý, có thể chia hệ thống thành sáu khối chức năng:

- **Khối nguồn:** Bộ pin BT1, công tắc SW1, module DC-DC Buck U2, các điện trở R1 và R2.
- **Khối xử lý trung tâm:** ESP32 DevKit V1 30 chân, ký hiệu U1.
- **Khối điều khiển chuyển động:** Module L298N U3 và hai động cơ DC M1, M2.
- **Khối phát hiện vật cản:** Cảm biến HC-SR04 U4 kết hợp servo SG90 M3.
- **Khối đóng ngắt và cảnh báo:** Module relay U5, buzzer BZ1 và LED D1.
- **Khối kết nối:** Các connector J1, J2, J3, J4 và J5.

Các khối phối hợp với nhau thông qua những đường nguồn và tín hiệu đã được xác định trong schematic.

## 2. Mô tả chi tiết các linh kiện và chức năng

### 2.1. Vi điều khiển ESP32 DevKit V1 – U1

#### 2.1.1. Giới thiệu và chức năng

ESP32 DevKit V1 là bo mạch phát triển sử dụng vi điều khiển ESP32, tích hợp khả năng xử lý dữ liệu và giao tiếp không dây Wi-Fi, Bluetooth. ESP32 có bộ xử lý 32 bit, tốc độ hoạt động có thể đạt đến 240 MHz tùy cấu hình và chương trình sử dụng.

Trong hệ thống SmartRobot, ESP32 đóng vai trò là bộ điều khiển trung tâm, thực hiện các nhiệm vụ:

- Tiếp nhận lệnh điều khiển chuyển động.
- Xuất tín hiệu điều khiển hai động cơ DC thông qua L298N.
- Tạo xung điều khiển cho cảm biến HC-SR04.
- Đo thời gian xung ECHO để tính khoảng cách vật cản.
- Điều khiển góc quay của servo SG90.
- Điều khiển relay đóng hoặc ngắt nguồn động cơ.
- Kích hoạt buzzer khi cần phát tín hiệu cảnh báo.

Khả năng Wi-Fi của ESP32 cho phép xây dựng hệ thống giao tiếp với giao diện điều khiển. Tuy nhiên, giao thức truyền lệnh cụ thể phụ thuộc vào chương trình điều khiển, không được thể hiện trực tiếp trong sơ đồ mạch điện.

#### 2.1.2. Cấu tạo và đặc điểm

Bo ESP32 DevKit V1 sử dụng trong sơ đồ có 30 chân kết nối, chia thành hai hàng, mỗi hàng 15 chân. Trên bo có các thành phần cơ bản như vi điều khiển ESP32, mạch ổn áp, mạch USB-UART, cổng USB và các linh kiện hỗ trợ khởi động.

Các chân GPIO hỗ trợ nhiều chức năng, bao gồm đầu vào số, đầu ra số, PWM, ADC và các giao thức truyền thông. Trong hệ thống này, những chân GPIO được sử dụng chủ yếu để giao tiếp với cảm biến và điều khiển các thiết bị ngoại vi.

#### 2.1.3. Chi tiết các chân ESP32 theo schematic

Số chân dưới đây là số chân của **symbol U1 tự tạo trong KiCad**, không phải số chân trên IC ESP32 bên trong module.

| Số chân | Tên chân | Chức năng trong hệ thống |
|---:|---|---|
| 1 | EN | Chân cho phép hoạt động/reset; không nối ra mạch ngoài |
| 2 | GPIO36 | GPIO đầu vào, chưa sử dụng |
| 3 | GPIO39 | GPIO đầu vào, chưa sử dụng |
| 4 | GPIO34 | GPIO đầu vào, chưa sử dụng |
| 5 | GPIO35 | GPIO đầu vào, chưa sử dụng |
| 6 | GPIO32 | Chưa sử dụng |
| 7 | GPIO33 | Chưa sử dụng |
| 8 | GPIO25 | Chưa sử dụng |
| 9 | GPIO26 | Điều khiển relay qua `RELAY_IN` |
| 10 | GPIO27 | Xuất xung kích hoạt cảm biến qua `US_TRIG` |
| 11 | GPIO14 | Nhận tín hiệu ECHO qua `US_ECHO_RAW` |
| 12 | GPIO12 | Điều khiển buzzer qua `BUZZER_CTRL` |
| 13 | GPIO13 | Điều khiển servo qua `SERVO_SIG` |
| 14 | GND | Chân mass chung |
| 15 | VIN | Nhận nguồn qua điện trở R2 |
| 16 | 3V3 | Chân nguồn 3,3 V, không đấu ra ngoại vi |
| 17 | GND | Chân mass chung |
| 18 | GPIO15 | Chưa sử dụng |
| 19 | GPIO2 | Chưa sử dụng |
| 20 | GPIO4 | Chưa sử dụng |
| 21 | GPIO16 | Chưa sử dụng |
| 22 | GPIO17 | Chưa sử dụng |
| 23 | GPIO5 | Điều khiển L298N IN3 |
| 24 | GPIO18 | Điều khiển L298N IN4 |
| 25 | GPIO19 | Điều khiển L298N IN1 |
| 26 | GPIO21 | Điều khiển L298N IN2 |
| 27 | GPIO3 | Chưa sử dụng trong mạch ngoài |
| 28 | GPIO1 | Chưa sử dụng trong mạch ngoài |
| 29 | GPIO22 | Chưa sử dụng |
| 30 | GPIO23 | Chưa sử dụng |

Các chân không sử dụng đã được đánh dấu No Connect trong schematic. Đối với những chân như EN, GPIO1 và GPIO3, điều này chỉ biểu thị rằng không có dây đấu thêm từ mạch ngoài; chúng vẫn có thể được sử dụng bởi mạch tích hợp trên bo DevKit.

#### 2.1.4. Nguyên lý làm việc của ESP32

Khi được cấp nguồn phù hợp, ESP32 khởi động và thực thi chương trình điều khiển đã được nạp vào bộ nhớ.

Trong quá trình hoạt động, ESP32 liên tục thực hiện các tác vụ xử lý lệnh, đọc dữ liệu cảm biến và cập nhật trạng thái các chân đầu ra. Căn cứ vào chế độ vận hành, chương trình có thể quyết định hướng quay của động cơ, vị trí servo, trạng thái relay hoặc tín hiệu buzzer.

Nhờ khả năng xử lý đồng thời các tín hiệu vào và ra, ESP32 đóng vai trò liên kết các khối riêng lẻ thành một hệ thống điều khiển thống nhất.

### 2.2. Bộ pin Li-ion – BT1

#### 2.2.1. Chức năng

Bộ pin cung cấp năng lượng điện cho toàn bộ hệ thống SmartRobot, giúp xe hoạt động mà không cần kết nối liên tục với nguồn điện bên ngoài.

Theo cấu hình phần cứng đã mô tả, xe sử dụng ba viên pin Li-ion mắc nối tiếp (3S). Nếu là ba cell Li-ion có điện áp danh định 3,7 V/cell, bộ pin có điện áp danh định khoảng 11,1 V và điện áp tối đa khoảng 12,6 V khi được sạc đầy.

Trong schematic, BT1 được thể hiện bằng ký hiệu pin tổng quát, chưa thể hiện riêng ba cell hoặc mạch bảo vệ pin.

#### 2.2.2. Các chân

| Chân | Ký hiệu | Chức năng |
|---|---|---|
| 1 | + | Cực dương, nối với mạng `BAT_PROTECTED+` |
| 2 | − | Cực âm, nối với mạng GND |

Cực dương của bộ pin được đưa đến công tắc SW1 và connector J1. Sau công tắc SW1, nguồn được đưa vào mạch DC-DC Buck để chuyển đổi điện áp.

Cực âm của bộ pin được sử dụng làm điểm tham chiếu điện áp chung cho các khối trong hệ thống.

#### 2.2.3. Nguyên lý hoạt động

Khi công tắc nguồn được đóng, nguồn điện từ bộ pin được đưa tới đầu vào module Buck. Module Buck có nhiệm vụ giảm mức điện áp của bộ pin xuống mức 5 V theo cấu hình dự kiến của hệ thống.

Tên mạng `BAT_PROTECTED+` trong schematic biểu thị đường dương nguồn được quy ước là đã bảo vệ. Tuy nhiên, bản vẽ chưa thể hiện mạch BMS, nên chưa thể xác nhận chức năng chống quá sạc, quá xả hoặc quá dòng của bộ pin chỉ từ schematic.

### 2.3. Công tắc nguồn SW1

#### 2.3.1. Chức năng

SW1 là công tắc một cực một trạng thái đóng/ngắt (SPST), được sử dụng để điều khiển nguồn điện đầu vào của hệ thống.

#### 2.3.2. Các chân

| Chân | Tên | Kết nối |
|---:|---|---|
| 1 | A | `BAT_PROTECTED+` |
| 2 | B | `BAT_SW` |

#### 2.3.3. Nguyên lý hoạt động

Khi SW1 ở trạng thái mở, đường dương từ bộ pin đến đầu vào Buck bị ngắt.

Khi SW1 ở trạng thái đóng, hai chân A và B được nối điện với nhau, cho phép dòng điện truyền từ bộ pin đến module Buck. Do đó, SW1 đóng vai trò là công tắc nguồn chính của hệ thống.

### 2.4. Module giảm áp DC-DC Buck – U2

#### 2.4.1. Giới thiệu và chức năng

DC-DC Buck là bộ chuyển đổi điện áp một chiều sang một chiều có chức năng giảm điện áp đầu vào xuống một mức điện áp thấp hơn.

Trong hệ thống SmartRobot, module Buck nhận điện áp từ bộ pin sau công tắc SW1 và được thiết kế để tạo đường nguồn `+5V_SYS` cung cấp cho các thiết bị.

So với phương pháp giảm áp bằng điện trở, mạch Buck có khả năng điều chỉnh điện áp đầu ra theo nguyên lý chuyển mạch, giúp cung cấp nguồn ổn định hơn khi tải thay đổi, trong giới hạn thiết kế của module.

#### 2.4.2. Các chân kết nối

| Chân | Tên | Chức năng và kết nối |
|---:|---|---|
| 1 | VIN+ | Nhận điện áp dương từ `BAT_SW` |
| 2 | VIN− | Nối GND đầu vào |
| 3 | VOUT+ | Cấp nguồn `+5V_SYS` |
| 4 | VOUT− | Nối GND đầu ra |

#### 2.4.3. Nguyên lý hoạt động

Khi điện áp được cấp vào VIN+ và VIN−, mạch Buck sử dụng quá trình đóng ngắt linh kiện bán dẫn kết hợp với phần tử tích trữ năng lượng để chuyển đổi điện áp đầu vào thành điện áp thấp hơn.

Trong schematic, đầu ra dương của Buck được nối vào mạng `+5V_SYS`. Mạng này cấp nguồn cho module L298N ở phần logic, cảm biến HC-SR04, servo SG90, module relay và mạch LED báo nguồn. Ngoài ra, nguồn này còn được đưa tới tầng ESP32 thông qua đầu nối 6 chân.

Đường nguồn cấp cho động cơ được tách riêng về mặt chức năng bằng relay, mặc dù cùng lấy nguồn ban đầu từ `+5V_SYS`.

### 2.5. Điện trở R2 trên đường cấp nguồn ESP32

#### 2.5.1. Chức năng được thể hiện trong schematic

R2 là điện trở được đặt nối tiếp giữa đường nguồn `+5V_SYS` và chân VIN của ESP32.

Trong bản vẽ, R2 được ghi giá trị **10 Ω / 2 W**.

#### 2.5.2. Các đầu nối

| Đầu | Kết nối |
|---|---|
| Đầu 1 | `VIN_AFTER_R2`, nối ESP32 VIN |
| Đầu 2 | `+5V_SYS` |

#### 2.5.3. Nguyên lý điện

Điện trở nối tiếp tạo ra độ sụt áp tỷ lệ với dòng điện chạy qua nó, theo định luật Ohm:

`U_R = I × R`

Trong đó:

- `U_R`: điện áp rơi trên điện trở.
- `I`: dòng điện chạy qua điện trở.
- `R`: giá trị điện trở.

Vì dòng điện tiêu thụ của ESP32 thay đổi trong quá trình hoạt động, điện áp sau R2 cũng thay đổi theo. Do đó, R2 không phải là mạch ổn áp và không thể bảo đảm tạo ra một mức điện áp cố định cho ESP32.

Trong báo cáo, R2 nên được mô tả là **điện trở nối tiếp trên đường nguồn theo sơ đồ hiện có**, thay vì khẳng định là bộ giảm áp an toàn. Giá trị và cách mắc này cần được kiểm tra trước khi cấp nguồn cho mạch.

### 2.6. Module điều khiển động cơ L298N – U3

#### 2.6.1. Giới thiệu

L298N là module điều khiển động cơ sử dụng IC cầu H kép (Dual H-Bridge). Module cho phép điều khiển chiều dòng điện đi qua hai động cơ điện một chiều một cách độc lập.

Các chân điều khiển có thể nhận tín hiệu số từ vi điều khiển, trong khi mạch cầu H thực hiện việc chuyển đổi trạng thái đóng ngắt của các nhánh công suất để cấp dòng cho động cơ.

Trong hệ thống SmartRobot, L298N nhận bốn tín hiệu điều khiển từ ESP32 để điều khiển hai động cơ DC M1 và M2.

#### 2.6.2. Các chân của module L298N

| Số chân symbol | Tên chân | Chức năng |
|---:|---|---|
| 1 | ENA | Cho phép kênh điều khiển động cơ A |
| 2 | IN1 | Tín hiệu điều khiển thứ nhất của động cơ A |
| 3 | IN2 | Tín hiệu điều khiển thứ hai của động cơ A |
| 4 | IN3 | Tín hiệu điều khiển thứ nhất của động cơ B |
| 5 | IN4 | Tín hiệu điều khiển thứ hai của động cơ B |
| 6 | ENB | Cho phép kênh điều khiển động cơ B |
| 7 | VS | Nguồn công suất cấp cho động cơ |
| 8 | GND | Mass chung |
| 9 | 5V_LG | Nguồn 5 V cấp cho phần logic module |
| 10 | OUT1 | Ngõ ra thứ nhất của động cơ M1 |
| 11 | OUT2 | Ngõ ra thứ hai của động cơ M1 |
| 12 | OUT3 | Ngõ ra thứ nhất của động cơ M2 |
| 13 | OUT4 | Ngõ ra thứ hai của động cơ M2 |

Lưu ý: Đây là số chân của **symbol module L298N 13 chân tự tạo**, không phải thứ tự chân vật lý của IC L298N.

#### 2.6.3. Kết nối với ESP32

| ESP32 | Mạng tín hiệu | L298N |
|---|---|---|
| GPIO19 | `MOTOR_IN1` | IN1 |
| GPIO21 | `MOTOR_IN2` | IN2 |
| GPIO5 | `MOTOR_IN3` | IN3 |
| GPIO18 | `MOTOR_IN4` | IN4 |

Theo schematic, hai chân ENA và ENB không được điều khiển bằng dây GPIO ngoài. Ghi chú trên bản vẽ cho biết jumper ENA và ENB trên module được lắp sẵn.

Điều này có nghĩa hai kênh điều khiển được giả định luôn ở trạng thái cho phép khi module hoạt động. Nếu không thực hiện PWM trên những đường tín hiệu khác, hệ thống chủ yếu điều khiển chiều quay và trạng thái động cơ, chưa có đường PWM độc lập đến hai chân ENA và ENB.

#### 2.6.4. Nguyên lý cầu H

Mỗi kênh của L298N sử dụng một mạch cầu H để đảo chiều dòng điện đi qua động cơ.

Đối với kênh A, khi ENA được kích hoạt, trạng thái của IN1 và IN2 quyết định chiều điện áp đặt lên hai đầu động cơ.

| IN1 | IN2 | Trạng thái kênh A |
|---|---|---|
| LOW | LOW | Hai đầu ra cùng mức, không tạo điện áp quay thuận/ngược |
| HIGH | LOW | Động cơ quay theo chiều thứ nhất |
| LOW | HIGH | Động cơ quay theo chiều ngược lại |
| HIGH | HIGH | Hai đầu ra cùng mức, tạo trạng thái hãm điện |

Đối với kênh B, nguyên lý tương tự, sử dụng IN3 và IN4.

Chiều quay thuận hoặc ngược thực tế phụ thuộc vào cách đấu hai dây của từng động cơ.

#### 2.6.5. Cách điều khiển chuyển động của xe

Xe có hai động cơ DC, vì vậy có thể thay đổi hướng di chuyển thông qua việc phối hợp trạng thái hai kênh:

- **Tiến:** Hai động cơ quay theo chiều làm xe chuyển động về phía trước.
- **Lùi:** Hai động cơ cùng đảo chiều.
- **Rẽ trái:** Điều chỉnh hướng hoặc trạng thái động cơ hai bên để tạo chênh lệch chuyển động.
- **Rẽ phải:** Điều chỉnh hai động cơ theo chiều ngược lại so với thao tác rẽ trái.
- **Dừng:** Ngừng tạo mô-men kéo cho các động cơ hoặc ngắt nguồn động cơ.

Đây là nguyên lý điều khiển vi sai thường dùng trên robot hai bánh chủ động.

#### 2.6.6. Nguồn cấp cho L298N

Sơ đồ phân biệt hai nguồn của module:

- `5V_LG`: Nguồn 5 V cho mạch logic, nối trực tiếp với `+5V_SYS`.
- `VS`: Nguồn cấp cho động cơ, nối với `+5V_MOTOR_SW` từ tiếp điểm NO của relay.

Trong ghi chú của schematic, jumper bộ ổn áp 5 V trên module được quy ước là tháo ra để sử dụng nguồn logic 5 V bên ngoài.

Như vậy, relay có thể ngắt nguồn công suất của động cơ trong khi phần logic L298N vẫn được cấp nguồn.

### 2.7. Hai động cơ DC – M1 và M2

#### 2.7.1. Chức năng

M1 và M2 là hai động cơ điện một chiều, có chức năng biến đổi năng lượng điện thành chuyển động quay, từ đó tạo lực kéo giúp xe di chuyển.

Trong sơ đồ, hai động cơ được điều khiển độc lập bởi hai kênh của module L298N.

#### 2.7.2. Các chân và kết nối

| Động cơ | Chân | Nối với |
|---|---|---|
| M1 | 1 (+) | L298N OUT1 |
| M1 | 2 (−) | L298N OUT2 |
| M2 | 1 (+) | L298N OUT3 |
| M2 | 2 (−) | L298N OUT4 |

Ký hiệu (+) và (−) trên symbol giúp phân biệt hai đầu dây theo quy ước, nhưng điện áp trên hai đầu động cơ có thể bị đảo cực khi L298N đổi chiều quay.

#### 2.7.3. Nguyên lý hoạt động

Khi xuất hiện điện áp giữa hai đầu động cơ, dòng điện chạy qua các cuộn dây bên trong làm rotor quay.

Khi cực tính điện áp bị đảo, hướng dòng điện qua phần ứng thay đổi, dẫn đến chiều quay của động cơ thay đổi.

Bằng cách điều khiển hai động cơ độc lập, hệ thống có thể tạo ra các chuyển động tiến, lùi và rẽ hướng.

### 2.8. Cảm biến siêu âm HC-SR04 – U4

#### 2.8.1. Giới thiệu

HC-SR04 là cảm biến đo khoảng cách bằng sóng siêu âm. Module sử dụng bộ phát và bộ thu siêu âm để xác định khoảng cách từ cảm biến đến vật thể phía trước.

Nguyên lý hoạt động dựa trên việc đo thời gian truyền và phản xạ của sóng âm. Do không cần tiếp xúc trực tiếp với vật thể, cảm biến phù hợp với các ứng dụng phát hiện vật cản trên robot di động.

HC-SR04 thông dụng sử dụng nguồn 5 V và sóng siêu âm có tần số khoảng 40 kHz.

#### 2.8.2. Các chân kết nối

| Số chân | Tên chân | Chức năng và kết nối |
|---:|---|---|
| 1 | VCC | Nhận nguồn `+5V_SYS` |
| 2 | TRIG | Nhận `US_TRIG` từ ESP32 GPIO27 |
| 3 | ECHO | Xuất `US_ECHO_RAW` về ESP32 GPIO14 |
| 4 | GND | Nối mass chung |

#### 2.8.3. Nguyên lý đo khoảng cách

Quá trình đo khoảng cách của HC-SR04 được thực hiện theo các bước:

**Bước 1:** ESP32 tạo một xung điều khiển tại GPIO27, đưa đến chân TRIG của cảm biến. Đối với HC-SR04 thông dụng, xung kích hoạt có độ rộng khoảng 10 µs.

**Bước 2:** Sau khi nhận tín hiệu kích hoạt, cảm biến phát một chùm gồm các xung siêu âm tần số khoảng 40 kHz.

**Bước 3:** Sóng siêu âm truyền trong không khí, gặp vật cản và phản xạ trở lại bộ thu.

**Bước 4:** Cảm biến tạo tín hiệu tại chân ECHO, có độ rộng xung phụ thuộc vào thời gian sóng âm truyền đi và quay trở lại.

**Bước 5:** ESP32 đo độ rộng xung ECHO tại GPIO14, từ đó tính khoảng cách đến vật cản.

Công thức tính khoảng cách:

`d = (v × t) / 2`

Trong đó:

- `d`: khoảng cách giữa cảm biến và vật cản.
- `v`: tốc độ truyền âm trong không khí.
- `t`: thời gian sóng âm truyền đi và quay trở lại.

Trong điều kiện thông thường, có thể dùng công thức gần đúng:

`Khoảng cách (cm) ≈ Thời gian ECHO (µs) / 58`

Hệ số chia 2 xuất hiện vì thời gian đo bao gồm cả hành trình sóng âm đi từ cảm biến đến vật cản và hành trình phản xạ trở lại.

#### 2.8.4. Vai trò trong hệ thống

Dữ liệu khoảng cách thu được là cơ sở để ESP32 phát hiện vật cản. Khi khoảng cách giảm xuống dưới ngưỡng được quy định trong chương trình, hệ thống có thể thực hiện các hành động như giảm chuyển động, dừng xe hoặc thay đổi hướng di chuyển.

Ngưỡng khoảng cách cụ thể thuộc về phần mềm điều khiển, không được thể hiện trong schematic.

### 2.9. Động cơ servo SG90 – M3

#### 2.9.1. Giới thiệu

SG90 là động cơ servo kích thước nhỏ, được thiết kế để điều khiển vị trí góc quay dựa trên tín hiệu điều khiển dạng xung.

Khác với động cơ DC thông thường, servo được sử dụng để di chuyển đến một vị trí góc mong muốn và duy trì vị trí đó trong khả năng của cơ cấu điều khiển.

Trong hệ thống SmartRobot, servo được dùng để thay đổi hướng của cảm biến siêu âm HC-SR04, hỗ trợ khảo sát khoảng cách vật cản ở nhiều hướng.

#### 2.9.2. Các chân kết nối

| Số chân | Tên chân | Chức năng |
|---:|---|---|
| 1 | PWM | Nhận `SERVO_SIG` từ ESP32 GPIO13 |
| 2 | + | Nhận nguồn `+5V_SYS` |
| 3 | − | Nối GND |

#### 2.9.3. Nguyên lý hoạt động

ESP32 tạo tín hiệu điều khiển servo tại GPIO13. Servo nhận tín hiệu có độ rộng xung tương ứng với vị trí góc cần đạt.

Bên trong servo có động cơ, bộ truyền bánh răng và hệ thống phản hồi vị trí. Mạch điều khiển servo so sánh vị trí mong muốn với vị trí thực tế để điều khiển động cơ quay đến vị trí phù hợp.

Khi kết hợp với HC-SR04, servo cho phép thay đổi hướng phát hiện vật cản mà không cần xoay toàn bộ thân xe.

Ví dụ, chương trình điều khiển có thể quay servo sang bên trái, đo khoảng cách, sau đó quay sang bên phải để tiếp tục đo. Dữ liệu này được dùng để lựa chọn hướng di chuyển có không gian thông thoáng hơn.

### 2.10. Module Relay một kênh 5 V – U5

#### 2.10.1. Giới thiệu

Relay là thiết bị đóng ngắt mạch điện bằng cơ cấu tiếp điểm. Module relay một kênh cho phép tín hiệu điều khiển điện áp thấp tác động đến một mạch điện tải riêng biệt.

Trong SmartRobot, relay được sử dụng để điều khiển việc cấp hoặc ngắt nguồn công suất cho module L298N.

#### 2.10.2. Các chân relay

| Số chân | Tên chân | Chức năng và kết nối |
|---:|---|---|
| 1 | VCC | Nguồn 5 V cho mạch điều khiển relay |
| 2 | GND | Mass chung |
| 3 | IN | Nhận `RELAY_IN` từ GPIO26 |
| 4 | COM | Tiếp điểm chung, nối `+5V_SYS` |
| 5 | NO | Tiếp điểm thường mở, nối `+5V_MOTOR_SW` |
| 6 | NC | Tiếp điểm thường đóng, không sử dụng |

#### 2.10.3. Phân biệt VCC và COM

Mặc dù VCC và COM đều được nối đến nguồn `+5V_SYS`, chúng đảm nhiệm hai chức năng khác nhau.

**VCC** cung cấp điện năng cho phần điều khiển của module relay, bao gồm mạch kích và cuộn dây relay.

**COM** là chân tiếp điểm của mạch công suất, có chức năng truyền hoặc ngắt nguồn điện đến tải tùy trạng thái relay.

Việc hai chân này được nối đến cùng một nguồn không có nghĩa chúng có chức năng giống nhau.

#### 2.10.4. Nguyên lý hoạt động

Trong schematic, COM được nối với `+5V_SYS`, còn NO được nối với `+5V_MOTOR_SW`. Đường `+5V_MOTOR_SW` tiếp tục cấp nguồn cho chân VS của L298N.

Khi relay chưa đóng tiếp điểm COM–NO, đường nguồn cấp cho động cơ ở L298N bị ngắt.

Khi relay đóng tiếp điểm COM–NO, nguồn 5 V được truyền từ COM sang NO và đi tới chân VS của L298N. Khi đó, hai động cơ có thể hoạt động theo tín hiệu điều khiển từ ESP32.

Nếu module relay thực tế thuộc loại kích mức thấp (Active LOW), trạng thái LOW ở chân IN sẽ kích relay. Tuy nhiên, loại kích mức cao hay thấp phụ thuộc vào module thực tế; schematic chỉ thể hiện đường kết nối GPIO26 đến chân IN.

### 2.11. Buzzer – BZ1

#### 2.11.1. Chức năng

Buzzer là linh kiện phát âm thanh, được sử dụng để tạo tín hiệu cảnh báo trong hệ thống SmartRobot.

Buzzer có thể được chương trình điều khiển kích hoạt khi xe phát hiện vật cản hoặc khi xảy ra một trạng thái cần thông báo bằng âm thanh.

#### 2.11.2. Các chân kết nối

| Số chân | Tên chân | Kết nối |
|---:|---|---|
| 1 | + | `BUZZER_CTRL`, ESP32 GPIO12 |
| 2 | − | GND |

#### 2.11.3. Nguyên lý hoạt động

Theo schematic, chân dương của buzzer được điều khiển trực tiếp từ GPIO12, còn chân âm nối GND.

Nếu sử dụng buzzer chủ động tương thích điện áp và dòng GPIO, khi GPIO12 được đưa lên mức HIGH, buzzer có thể phát ra âm thanh. Khi GPIO12 ở mức LOW, buzzer ngừng hoạt động.

ESP32 có thể thay đổi trạng thái GPIO12 theo thời gian để tạo ra các nhịp cảnh báo.

Sơ đồ chưa xác định mã linh kiện và dòng tiêu thụ cụ thể của buzzer, do đó cần phân biệt cấu hình giả định này với thông số thực tế của linh kiện.

### 2.12. LED báo nguồn D1 và điện trở R1

#### 2.12.1. Chức năng

LED D1 được sử dụng để hiển thị trạng thái có nguồn 5 V trong hệ thống.

Điện trở R1 được mắc nối tiếp với LED nhằm hạn chế dòng điện chạy qua LED, giúp LED hoạt động trong mức dòng điện phù hợp.

#### 2.12.2. Các chân và giá trị

**Điện trở R1:**

- Giá trị: 1 kΩ.
- Một đầu nối `+5V_SYS`.
- Đầu còn lại nối với Anode của LED D1.

**LED D1:**

| Chân | Tên | Kết nối |
|---:|---|---|
| 2 | A – Anode | Nối với R1 |
| 1 | K – Cathode | Nối GND |

#### 2.12.3. Nguyên lý hoạt động

Khi module Buck cung cấp nguồn `+5V_SYS`, dòng điện đi qua điện trở R1, sau đó qua LED D1 về GND, làm LED phát sáng.

Với giả định LED đỏ có điện áp thuận khoảng 2 V và nguồn cấp là 5 V, dòng điện gần đúng là:

`I = (5 − 2) / 1000 = 0,003 A = 3 mA`

Như vậy, R1 giúp hạn chế dòng qua LED ở mức khoảng 3 mA theo giả định tính toán trên.

LED sáng khi có nguồn 5 V phù hợp và tắt khi nguồn bị ngắt. LED chỉ biểu thị sự hiện diện của nguồn ở vị trí kết nối, không tự động xác nhận rằng tất cả module đang hoạt động bình thường.

## 3. Hệ thống đầu nối giữa hai tầng

### 3.1. Connector nguồn J1

J1 là đầu nối hai chân, được sử dụng để thể hiện đường nguồn từ bộ pin.

| Chân | Mạng điện | Chức năng |
|---:|---|---|
| 1 | `BAT_PROTECTED+` | Đường dương của bộ pin |
| 2 | `GND` | Đường âm của bộ pin |

Đầu nối J1 giúp tổ chức đường cấp nguồn, hỗ trợ kết nối và tháo lắp giữa các bộ phận của xe.

### 3.2. Connector điều khiển động cơ J2 và J3

Trong schematic, J2 và J3 là hai đầu nối bốn chân có cùng thứ tự tín hiệu, dùng để truyền các lệnh điều khiển từ ESP32 đến L298N.

| Chân | Net Label | Chức năng |
|---:|---|---|
| 1 | `MOTOR_IN1` | Điều khiển L298N IN1 |
| 2 | `MOTOR_IN2` | Điều khiển L298N IN2 |
| 3 | `MOTOR_IN3` | Điều khiển L298N IN3 |
| 4 | `MOTOR_IN4` | Điều khiển L298N IN4 |

Thông qua bốn đường tín hiệu này, ESP32 có thể điều khiển độc lập hai kênh cầu H của L298N.

### 3.3. Connector ngoại vi J4 và J5

J4 và J5 là hai đầu nối sáu chân có cùng thứ tự mạng điện.

| Chân | Net Label | Chức năng |
|---:|---|---|
| 1 | `+5V_SYS` | Đường cấp nguồn 5 V lên tầng ESP32 |
| 2 | `US_TRIG` | Tín hiệu kích hoạt cảm biến siêu âm |
| 3 | `US_ECHO_RAW` | Tín hiệu phản hồi từ cảm biến |
| 4 | `SERVO_SIG` | Tín hiệu điều khiển servo |
| 5 | `RELAY_IN` | Tín hiệu điều khiển relay |
| 6 | `BUZZER_CTRL` | Tín hiệu điều khiển buzzer |

Các connector giúp tách hai tầng thành những cụm lắp ráp riêng, đồng thời thuận tiện hơn trong việc kết nối, tháo lắp và bảo trì.

Trong hai cặp đầu nối tín hiệu 4 chân và 6 chân không có chân GND riêng. Vì vậy, hệ thống phải bảo đảm có đường GND chung vật lý giữa hai tầng thông qua hệ thống dây nguồn, tương ứng với mạng GND được thể hiện trên schematic.

## 4. Nguyên lý hoạt động của toàn bộ sơ đồ

### 4.1. Quá trình cấp nguồn

Khi người dùng đóng công tắc SW1, điện áp từ bộ pin BT1 được đưa đến đầu vào module Buck U2 thông qua mạng `BAT_SW`.

Module Buck được dùng để tạo nguồn 5 V trên mạng `+5V_SYS`.

Nguồn này được phân phối đến các thiết bị gồm cảm biến HC-SR04, servo SG90, module relay, phần logic của L298N và LED báo nguồn.

Đối với ESP32, đường `+5V_SYS` được đưa qua điện trở R2 trước khi đến chân VIN theo cấu hình schematic.

Đối với động cơ DC, nguồn từ `+5V_SYS` đi qua tiếp điểm COM–NO của relay rồi đến chân VS của L298N. Vì vậy, nguồn công suất của động cơ có thể được đóng/ngắt độc lập với đường nguồn logic.

### 4.2. Quá trình khởi động hệ thống

Khi ESP32 nhận được điện áp hoạt động hợp lệ, vi điều khiển bắt đầu khởi động và thực thi chương trình đã nạp.

Chương trình thiết lập hướng hoạt động cho các chân GPIO:

- GPIO19, GPIO21, GPIO5 và GPIO18: Điều khiển động cơ.
- GPIO27: Phát xung kích hoạt cảm biến.
- GPIO14: Đọc xung phản hồi cảm biến.
- GPIO13: Điều khiển servo.
- GPIO26: Điều khiển relay.
- GPIO12: Điều khiển buzzer.

Sau quá trình khởi tạo, ESP32 có thể tiếp nhận lệnh điều khiển và thực hiện các tác vụ theo chế độ hoạt động được chương trình lựa chọn.

### 4.3. Nguyên lý hoạt động ở chế độ điều khiển thủ công

Ở chế độ điều khiển thủ công, người sử dụng gửi lệnh di chuyển từ giao diện điều khiển đến hệ thống ESP32.

ESP32 tiếp nhận và xử lý lệnh, sau đó chuyển thành các tín hiệu mức HIGH/LOW tại các chân GPIO điều khiển L298N.

Ví dụ, khi có lệnh tiến, ESP32 thiết lập trạng thái các chân IN1, IN2, IN3 và IN4 sao cho hai động cơ quay theo hướng làm xe tiến về phía trước.

Khi có lệnh lùi, trạng thái điều khiển được đảo lại để thay đổi chiều quay của hai động cơ.

Khi có lệnh rẽ, ESP32 tạo sự khác biệt về trạng thái quay giữa hai động cơ. Nhờ đó, xe thay đổi hướng di chuyển.

Khi cần dừng, ESP32 có thể đưa các chân điều khiển động cơ về trạng thái phù hợp hoặc sử dụng relay để ngắt nguồn công suất, tùy theo logic phần mềm.

Như vậy, ESP32 là bộ xử lý lệnh, còn L298N thực hiện chức năng điều khiển công suất cho các động cơ DC.

### 4.4. Nguyên lý hoạt động ở chế độ tự động tránh vật cản

Trong chế độ tự động, ESP32 sử dụng dữ liệu khoảng cách thu được từ cảm biến HC-SR04 để quyết định hướng di chuyển.

Quá trình hoạt động có thể được mô tả như sau:

**Bước 1 – Phát hiện vật cản:** ESP32 phát xung kích hoạt qua GPIO27 đến chân TRIG của HC-SR04. Cảm biến phát sóng siêu âm, nhận tín hiệu phản xạ và đưa xung ECHO về GPIO14.

**Bước 2 – Tính toán khoảng cách:** ESP32 đo độ rộng xung ECHO để tính khoảng cách giữa xe và vật cản.

**Bước 3 – Đánh giá tình huống:** Chương trình so sánh khoảng cách đo được với ngưỡng an toàn được thiết lập trong phần mềm.

**Bước 4 – Kiểm tra các hướng di chuyển:** Nếu phát hiện vật cản quá gần, ESP32 có thể điều khiển SG90 quay cảm biến sang các hướng khác nhau để tiếp tục đo khoảng cách.

**Bước 5 – Lựa chọn hướng:** Căn cứ vào các giá trị khoảng cách thu được, ESP32 quyết định hướng di chuyển phù hợp.

**Bước 6 – Điều khiển động cơ:** ESP32 xuất các tín hiệu điều khiển đến L298N để xe tiến, lùi hoặc rẽ nhằm tránh vật cản.

**Bước 7 – Cập nhật liên tục:** Quá trình đo khoảng cách và điều khiển được thực hiện lặp lại để xe thích ứng với sự thay đổi của môi trường.

Đây là nguyên lý chức năng của chế độ tránh vật cản. Thứ tự quét servo, các ngưỡng khoảng cách và quy tắc ưu tiên hướng rẽ cần đối chiếu thêm với mã chương trình nếu muốn mô tả chính xác thuật toán đã triển khai.

### 4.5. Nguyên lý hoạt động của hệ thống cảnh báo

Hệ thống sử dụng buzzer BZ1 để tạo cảnh báo âm thanh.

Khi chương trình xác định cần thông báo một trạng thái, ESP32 điều khiển GPIO12 thông qua mạng `BUZZER_CTRL`.

Đối với buzzer chủ động tương thích với GPIO, tín hiệu điều khiển ở mức phù hợp có thể làm buzzer phát âm thanh. Việc thay đổi trạng thái HIGH và LOW theo thời gian giúp tạo ra các nhịp cảnh báo.

Bên cạnh đó, LED D1 được mắc với điện trở hạn dòng R1 trên đường nguồn `+5V_SYS`, có nhiệm vụ thông báo trạng thái có nguồn của mạch.

Hai bộ phận này hỗ trợ người sử dụng quan sát và nhận biết một số trạng thái của hệ thống.

### 4.6. Nguyên lý đóng/ngắt nguồn động cơ

Module relay U5 nhận tín hiệu điều khiển từ ESP32 thông qua GPIO26.

Theo schematic, chân COM của relay được nối với nguồn `+5V_SYS`, còn chân NO được nối với đường `+5V_MOTOR_SW` cấp cho chân VS của L298N.

Khi tiếp điểm COM–NO đóng, nguồn điện được truyền đến mạch công suất của L298N. Hai động cơ có thể hoạt động theo tín hiệu điều khiển.

Khi tiếp điểm COM–NO mở, đường nguồn công suất cấp cho động cơ bị ngắt.

Việc sử dụng relay giúp hệ thống có thêm khả năng điều khiển trạng thái cấp nguồn cho khối động cơ, bên cạnh việc điều khiển chiều quay thông qua các chân IN1–IN4.

## 5. Đánh giá thiết kế và những điểm cần xác minh

Sơ đồ nguyên lý thể hiện được sự phân chia chức năng giữa khối xử lý trung tâm, khối nguồn, khối điều khiển động cơ, khối cảm biến và các thiết bị phụ trợ.

Các tín hiệu điều khiển được đặt tên rõ ràng, giúp thuận tiện trong quá trình kiểm tra kết nối và mô tả hoạt động của hệ thống. Việc sử dụng connector còn hỗ trợ cách tổ chức phần cứng thành hai tầng.

Tuy nhiên, một số điểm cần tiếp tục xác minh để đánh giá tính an toàn và khả năng vận hành thực tế:

**Thứ nhất, đường cấp nguồn ESP32:** R2 được mắc nối tiếp với VIN và có giá trị 10 Ω / 2 W. Điện trở nối tiếp không có khả năng giữ điện áp đầu ra ổn định khi tải thay đổi. Vì vậy, cần kiểm tra lại cấu hình cấp nguồn trước khi vận hành.

**Thứ hai, tín hiệu HC-SR04 ECHO:** Schematic thể hiện chân ECHO nối trực tiếp đến GPIO14 của ESP32. Với module HC-SR04 thông dụng cấp nguồn 5 V, ECHO có thể tạo mức HIGH xấp xỉ 5 V, vượt mức điện áp đầu vào cho phép của ESP32. Do đó, kết nối này cần được xác minh hoặc xử lý phù hợp trước khi cấp điện.

**Thứ ba, hệ thống pin:** Sơ đồ sử dụng ký hiệu pin BT1 và tên nguồn `BAT_PROTECTED+`, nhưng chưa biểu diễn chi tiết mạch BMS của bộ pin ba cell. Khả năng bảo vệ quá dòng, quá sạc, quá xả và cân bằng cell chưa được chứng minh bằng bản vẽ.

**Thứ tư, nguồn động cơ:** L298N được cấp nguồn động cơ qua đường 5 V và tiếp điểm relay. Cần lưu ý rằng mạch cầu H có sụt áp trên tầng công suất, nên điện áp thực tế đặt lên động cơ có thể thấp hơn điện áp cấp VS.

**Thứ năm, các thiết bị ngoại vi:** Cần xác minh điện áp và dòng hoạt động thực tế của buzzer, servo, relay, cũng như đường GND chung giữa các tầng. Đặc biệt, GPIO12 là chân có chức năng cấu hình khởi động của ESP32, vì vậy tải ngoài tại chân này không được làm sai mức logic khi khởi động.

Các vấn đề này không nhất thiết được công cụ ERC của KiCad phát hiện và cần được đánh giá riêng trong quá trình kiểm tra phần cứng.

## 6. Kết luận

Sơ đồ nguyên lý SmartRobot được xây dựng theo cấu trúc điều khiển tập trung, sử dụng ESP32 làm bộ xử lý chính để phối hợp hoạt động của các khối chức năng. Module L298N đảm nhiệm điều khiển hai động cơ DC, cảm biến HC-SR04 kết hợp servo SG90 hỗ trợ xác định khoảng cách và hướng vật cản, relay thực hiện đóng/ngắt nguồn công suất động cơ, trong khi buzzer và LED đảm nhiệm chức năng cảnh báo và hiển thị trạng thái nguồn.

Nhờ sự kết hợp giữa các khối xử lý, cảm biến và cơ cấu chấp hành, hệ thống có cơ sở phần cứng để thực hiện hai chế độ điều khiển thủ công và tự động tránh vật cản. Sơ đồ nguyên lý cũng là tài liệu quan trọng để giải thích hoạt động, kiểm tra kết nối và phục vụ quá trình bảo trì, cải tiến hệ thống. Trước khi sử dụng bản vẽ để chế tạo hoặc cấp điện, những giả định liên quan đến nguồn ESP32, mức tín hiệu ECHO và bảo vệ bộ pin cần được kiểm tra và hoàn thiện.