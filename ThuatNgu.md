# BẢNG THUẬT NGỮ PHẦN CỨNG VÀ KIẾN TRÚC WEB SMARTROBOT

Nguồn tổng hợp: [Hardware.MD](Hardware.MD) và [WebArchitecture.md](WebArchitecture.md).

Hai bảng bao gồm thuật ngữ kỹ thuật, chữ viết tắt, tên công nghệ, linh kiện, tín hiệu, đơn vị, trạng thái, trường dữ liệu và thao tác được sử dụng trong hai tài liệu. Thuật ngữ chung được nhắc lại trong từng bảng để có thể tra cứu độc lập; các biến thể cùng nhóm được gộp trong một dòng. Tên file, đường dẫn mã nguồn và số phiên bản chỉ đóng vai trò tham chiếu, không được liệt kê như thuật ngữ riêng. Phần diễn giải bám theo ngữ cảnh SmartRobot; tên tín hiệu do dự án đặt không phải tên tiêu chuẩn của linh kiện.

## 1. Bảng thuật ngữ trong Hardware.MD

| STT | Thuật ngữ / ký hiệu | Tên đầy đủ hoặc nghĩa tiếng Việt | Diễn giải trong hệ thống |
| --- | --- | --- | --- |
| 1 | SmartRobot | Tên hệ thống xe robot thông minh | Tên dự án tích hợp vi điều khiển, cảm biến, động cơ và phần mềm điều khiển. |
| 2 | Robot / xe robot | Thiết bị cơ điện có khả năng thực hiện tác vụ điều khiển | Trong dự án là xe hai động cơ, có điều khiển thủ công và tự động tránh vật cản. |
| 3 | Phần cứng | Hardware | Các linh kiện, mạch điện, nguồn, dây nối và cơ cấu cơ khí của xe. |
| 4 | Phần mềm / chương trình điều khiển | Software / control program | Các chỉ dẫn được nạp để ESP32 đọc cảm biến và điều khiển thiết bị. |
| 5 | Vi điều khiển | Microcontroller | Mạch tích hợp có bộ xử lý, bộ nhớ và ngoại vi để điều khiển hệ thống nhúng. |
| 6 | ESP32 | Họ vi điều khiển tích hợp kết nối không dây của Espressif | Bộ xử lý trung tâm nhận lệnh, đọc HC-SR04 và điều khiển motor, servo, relay, buzzer. |
| 7 | ESP32 DevKit V1 / DevKit | Bo mạch phát triển dùng ESP32 | Bo 30 chân được dùng trong schematic; bao gồm module ESP32 và mạch hỗ trợ. |
| 8 | Bo mạch phát triển | Development board | Bo giúp cấp nguồn, nạp chương trình và tiếp cận chân vi điều khiển. |
| 9 | IC | Integrated Circuit — mạch tích hợp | Linh kiện chứa nhiều phần tử điện tử; cần phân biệt chân IC với chân module/bo. |
| 10 | Module | Cụm mạch chức năng | Mạch đã tích hợp linh kiện hỗ trợ, chẳng hạn module L298N hoặc module relay. |
| 11 | Bộ xử lý 32 bit / bit | Độ rộng xử lý dữ liệu / đơn vị nhị phân | “32 bit” mô tả đặc tính xử lý của ESP32, không phải số chân bo mạch. |
| 12 | MHz | Megahertz | Một triệu chu kỳ mỗi giây; tài liệu dùng để mô tả tần số hoạt động bộ xử lý. |
| 13 | Wi-Fi | Công nghệ mạng không dây thuộc họ IEEE 802.11 | Cho phép ESP32 kết nối mạng để trao đổi dữ liệu với phần mềm điều khiển. |
| 14 | Bluetooth | Công nghệ kết nối không dây tầm gần | Khả năng của ESP32 được giới thiệu trong tài liệu; không đồng nghĩa dự án đang sử dụng đường truyền này. |
| 15 | USB | Universal Serial Bus | Chuẩn giao tiếp dùng ở cổng kết nối bo phát triển. |
| 16 | UART | Universal Asynchronous Receiver/Transmitter | Giao tiếp truyền/nhận dữ liệu nối tiếp bất đồng bộ. |
| 17 | USB-UART | Mạch chuyển đổi giữa USB và UART | Hỗ trợ máy tính giao tiếp nối tiếp và nạp chương trình cho bo. |
| 18 | GPIO | General-Purpose Input/Output — chân vào/ra đa dụng | Chân ESP32 có thể được cấu hình đọc tín hiệu hoặc xuất tín hiệu điều khiển. |
| 19 | GPIO19 / GPIO21 | Hai chân điều khiển L298N IN1 / IN2 | Theo sơ đồ lần lượt nối với `MOTOR_IN1` và `MOTOR_IN2`. |
| 20 | GPIO5 / GPIO18 | Hai chân điều khiển L298N IN3 / IN4 | Theo sơ đồ lần lượt nối với `MOTOR_IN3` và `MOTOR_IN4`. |
| 21 | GPIO27 | Chân phát tín hiệu kích hoạt siêu âm | Nối đến TRIG qua mạng `US_TRIG`. |
| 22 | GPIO14 | Chân nhận tín hiệu phản hồi siêu âm | Nối đến đường ECHO; cần kiểm tra mức điện áp trước khi đưa vào ESP32. |
| 23 | GPIO13 | Chân điều khiển servo | Nối đến mạng `SERVO_SIG`. |
| 24 | GPIO26 | Chân điều khiển relay | Nối đến mạng `RELAY_IN`. |
| 25 | GPIO12 | Chân điều khiển buzzer và có chức năng cấu hình khởi động | Tải ngoài không được làm sai mức logic lúc ESP32 khởi động. |
| 26 | GPIO36 / GPIO39 / GPIO34 / GPIO35 | Các GPIO chỉ hỗ trợ đầu vào trong nhóm được nêu | Chưa được sử dụng trong schematic hiện tại. |
| 27 | GPIO32 / GPIO33 / GPIO25 / GPIO15 / GPIO2 / GPIO4 / GPIO16 / GPIO17 / GPIO22 / GPIO23 | Các chân GPIO chưa sử dụng trong mạch ngoài | Số đi sau GPIO là số định danh chân, không phải số thứ tự trên symbol. |
| 28 | GPIO1 / GPIO3 | Hai GPIO không đấu thêm ra mạch ngoài | Vẫn có thể được mạch tích hợp trên bo DevKit sử dụng. |
| 29 | Đầu vào số / đầu ra số | Digital input / digital output | Đọc hoặc xuất trạng thái logic thay vì giá trị điện áp liên tục. |
| 30 | HIGH / LOW | Mức logic cao / thấp | Hai trạng thái tín hiệu số; điện áp thực tế phụ thuộc phần cứng. |
| 31 | Logic / mức logic | Trạng thái tín hiệu dùng để biểu diễn giá trị số | Dùng khi mô tả chân điều khiển và nguồn nuôi phần logic của module. |
| 32 | PWM | Pulse Width Modulation — điều chế độ rộng xung | Điều khiển bằng chuỗi xung có độ rộng thay đổi; được nhắc đến ở GPIO và servo. |
| 33 | ADC | Analog-to-Digital Converter — bộ chuyển đổi tương tự sang số | Chức năng ngoại vi của một số GPIO; không phải đường đo HC-SR04 trong sơ đồ. |
| 34 | EN | Enable — cho phép hoạt động | Chân cho phép/reset ESP32; không đấu thêm ra mạch ngoài trong schematic. |
| 35 | Reset / khởi động lại | Đưa hệ thống về quá trình khởi tạo | Vi điều khiển thực hiện lại chương trình từ trạng thái khởi động. |
| 36 | GND / mass / mass chung | Ground — điểm tham chiếu điện áp chung | Liên kết đường hồi dòng và mức tham chiếu giữa các khối, giữa hai tầng. |
| 37 | VIN / VIN+ / VIN− | Voltage Input — điện áp đầu vào | VIN trên ESP32 là chân cấp nguồn; VIN+/VIN− trên Buck là hai đầu nguồn vào. |
| 38 | VOUT+ / VOUT− | Voltage Output — hai cực điện áp đầu ra | Đầu ra của module Buck, tạo nguồn hệ thống và GND. |
| 39 | VCC | Chân cấp nguồn dương cho mạch | Nuôi HC-SR04 và phần điều khiển module relay trong sơ đồ. |
| 40 | 3V3 | Ký hiệu đường nguồn 3,3 V | Chân 3,3 V trên bo ESP32, chưa đấu ra ngoại vi trong schematic. |
| 41 | Schematic / sơ đồ nguyên lý | Bản vẽ các linh kiện và kết nối điện | Diễn tả quan hệ điện, không phải bản bố trí vật lý hoàn chỉnh. |
| 42 | KiCad | Phần mềm thiết kế điện tử | Dùng tạo symbol, vẽ schematic và kiểm tra kết nối. |
| 43 | Symbol | Ký hiệu linh kiện trong phần mềm thiết kế | Số chân symbol tự tạo không nhất thiết là thứ tự chân IC vật lý. |
| 44 | Net / mạng điện | Tập hợp các điểm được nối điện với nhau | Các điểm cùng mạng được xem là cùng kết nối điện trong sơ đồ. |
| 45 | Net Label | Nhãn tên mạng điện | Tên như `MOTOR_IN1` giúp nhận biết và tổ chức kết nối. |
| 46 | No Connect | Dấu chỉ chân không kết nối ra mạch ngoài | Không có nghĩa mọi chức năng nội bộ của chân trên bo đều bị vô hiệu hóa. |
| 47 | ERC | Electrical Rules Check — kiểm tra quy tắc điện | Công cụ kiểm tra schematic; không thay thế đánh giá điện áp, dòng tải và an toàn thực tế. |
| 48 | Connector / đầu nối | Bộ phận ghép nối dây hoặc bo mạch | Cho phép lắp ráp, tháo rời và nối tín hiệu giữa hai tầng. |
| 49 | J1 | Ký hiệu đầu nối nguồn hai chân | Dẫn `BAT_PROTECTED+` và GND từ bộ pin. |
| 50 | J2 / J3 | Ký hiệu cặp đầu nối điều khiển bốn chân | Mang bốn đường `MOTOR_IN1` đến `MOTOR_IN4`. |
| 51 | J4 / J5 | Ký hiệu cặp đầu nối ngoại vi sáu chân | Mang nguồn 5 V, TRIG, ECHO, servo, relay và buzzer. |
| 52 | U1 / U2 / U3 / U4 / U5 | Ký hiệu tham chiếu các bo/module | Lần lượt là ESP32, Buck, L298N, HC-SR04 và relay. |
| 53 | BT1 | Ký hiệu bộ pin | Nguồn năng lượng của toàn bộ xe. |
| 54 | Li-ion | Lithium-ion — loại pin ion lithium | Loại cell pin được mô tả cho bộ nguồn. |
| 55 | Cell | Một đơn vị pin điện hóa | Bộ pin có thể gồm nhiều cell ghép nối. |
| 56 | 3S / mắc nối tiếp | Ba cell mắc nối tiếp | Điện áp các cell cộng lại; với cell 3,7 V danh định, cả bộ khoảng 11,1 V. |
| 57 | Điện áp danh định | Nominal voltage | Mức điện áp quy ước để mô tả nguồn, không phải điện áp cố định ở mọi trạng thái. |
| 58 | BMS | Battery Management System — hệ thống quản lý pin | Có thể quản lý/bảo vệ pin; sơ đồ hiện chưa chứng minh đã có mạch này. |
| 59 | Quá sạc / quá xả / quá dòng / cân bằng cell | Các vấn đề và chức năng quản lý bộ pin | Liên quan giới hạn điện áp, dòng và độ lệch giữa các cell. |
| 60 | SW1 | Ký hiệu công tắc nguồn chính | Đóng/ngắt đường dương pin trước đầu vào Buck. |
| 61 | SPST | Single Pole Single Throw | Công tắc một cực, một ngả; dùng đóng hoặc ngắt một đường điện. |
| 62 | DC | Direct Current — dòng điện một chiều | Dùng khi mô tả nguồn và động cơ DC. |
| 63 | DC-DC Buck / Buck | Bộ chuyển đổi DC-DC giảm áp | Chuyển điện áp pin xuống đường nguồn 5 V theo cấu hình thiết kế. |
| 64 | Mạch ổn áp | Voltage regulator | Duy trì mức điện áp trong giới hạn hoạt động; khác với điện trở nối tiếp đơn thuần. |
| 65 | Nguyên lý chuyển mạch | Switching operation | Đóng/ngắt phần tử bán dẫn để điều khiển truyền năng lượng trong bộ nguồn. |
| 66 | Linh kiện bán dẫn / phần tử tích trữ năng lượng | Thành phần chuyển mạch và tích trữ năng lượng | Được mô tả như các phần tử tạo nên nguyên lý hoạt động Buck. |
| 67 | Điện áp / dòng điện / công suất | Các đại lượng điện cơ bản | Lần lượt mô tả chênh lệch điện thế, dòng điện tích và tốc độ truyền năng lượng. |
| 68 | Cực dương (+) / cực âm (−) / cực tính | Hai đầu và chiều quy ước của điện áp | Ở motor, điện áp trên hai đầu có thể đổi cực để đổi chiều quay. |
| 69 | Tải / mạch công suất / nguồn logic | Phần tiêu thụ điện / phần cấp dòng lớn / nguồn phần điều khiển | Relay ngắt nguồn motor trong khi logic L298N vẫn có thể được cấp điện. |
| 70 | Điện trở / R1 / R2 | Resistor / hai ký hiệu điện trở trong sơ đồ | R1 hạn dòng LED; R2 mắc nối tiếp đường VIN ESP32. |
| 71 | Điện trở hạn dòng / mắc nối tiếp | Điện trở giới hạn dòng / cách ghép trên cùng nhánh dòng | Dòng đi qua các phần tử mắc nối tiếp; R1 là ví dụ hạn dòng LED. |
| 72 | Sụt áp / điện áp rơi | Voltage drop | Phần điện áp giảm qua điện trở hoặc tầng công suất; phụ thuộc điều kiện hoạt động. |
| 73 | Định luật Ohm / `U_R = I × R` | Quan hệ điện áp, dòng điện và điện trở | `U_R` là điện áp trên điện trở, `I` là dòng qua nó, `R` là điện trở. |
| 74 | `BAT_PROTECTED+` | Tên mạng dương pin được quy ước đã bảo vệ | Chỉ là nhãn trong dự án; không tự chứng minh có BMS. |
| 75 | `BAT_SW` | Tên mạng dương pin sau công tắc | Nối từ SW1 đến đầu vào Buck. |
| 76 | `+5V_SYS` | Tên đường nguồn 5 V hệ thống | Cấp cho nhiều khối logic và ngoại vi. |
| 77 | `VIN_AFTER_R2` | Tên đường nguồn VIN sau R2 | Nối từ R2 đến VIN của ESP32. |
| 78 | `+5V_MOTOR_SW` | Tên đường nguồn 5 V motor sau relay | Đi đến chân VS của L298N qua tiếp điểm NO. |
| 79 | L298N | IC/module điều khiển hai động cơ | Nhận tín hiệu ESP32 và cấp dòng theo chiều cần thiết cho hai motor. |
| 80 | Cầu H / Dual H-Bridge | Mạch cầu H / hai cầu H | Đảo cực điện áp trên tải để đổi chiều quay động cơ DC. |
| 81 | ENA / ENB | Enable A / Enable B | Chân cho phép hai kênh L298N; schematic giả định có jumper enable. |
| 82 | Jumper | Cầu nối tháo/lắp được | Thiết lập cấu hình module; jumper enable và jumper ổn áp có chức năng khác nhau. |
| 83 | IN1 / IN2 / IN3 / IN4 | Bốn đầu vào điều khiển L298N | Hai đầu vào cho mỗi kênh cầu H. |
| 84 | OUT1 / OUT2 / OUT3 / OUT4 | Bốn đầu ra cấp cho hai motor | OUT1/OUT2 nối M1; OUT3/OUT4 nối M2. |
| 85 | VS | Chân nguồn công suất của L298N | Nhận nguồn motor đã qua relay. |
| 86 | `5V_LG` | Nhãn nguồn 5 V cho logic L298N | Được nối trực tiếp `+5V_SYS` theo sơ đồ. |
| 87 | `MOTOR_IN1` / `MOTOR_IN2` / `MOTOR_IN3` / `MOTOR_IN4` | Tên bốn mạng điều khiển motor | Nối các GPIO ESP32 tương ứng đến IN1–IN4 của L298N. |
| 88 | M1 / M2 / M3 | Ký hiệu ba động cơ | M1/M2 là motor DC kéo xe; M3 là servo SG90. |
| 89 | Động cơ DC | Direct-current motor | Biến điện năng thành chuyển động quay; đổi cực nguồn để đảo chiều. |
| 90 | Rotor / phần ứng / cuộn dây | Các bộ phận của động cơ | Liên quan đến việc tạo từ trường, dòng điện và chuyển động quay. |
| 91 | Mô-men kéo | Torque | Tác dụng làm quay bánh và kéo xe di chuyển. |
| 92 | Điều khiển vi sai / hai bánh chủ động | Differential drive | Thay đổi chuyển động hai bánh để xe tiến, lùi hoặc rẽ. |
| 93 | Hãm điện | Electrical braking | Trạng thái điều khiển động cơ để tạo tác dụng hãm; cần phân biệt với ngắt hẳn nguồn. |
| 94 | HC-SR04 / cảm biến siêu âm | Module đo khoảng cách bằng siêu âm | Đo thời gian sóng âm đi và phản xạ về để ước lượng khoảng cách. |
| 95 | Sóng siêu âm / phản xạ | Âm tần số cao / sóng dội lại từ vật | Cơ sở đo khoảng cách của HC-SR04. |
| 96 | TRIG / `US_TRIG` | Trigger / tên mạng kích hoạt siêu âm | ESP32 phát xung để HC-SR04 bắt đầu đo. |
| 97 | ECHO / `US_ECHO_RAW` | Xung phản hồi / tên mạng ECHO thô | Độ rộng xung phản ánh thời gian truyền đi và về; mức điện áp phải phù hợp GPIO. |
| 98 | Xung / độ rộng xung | Pulse / pulse width | Tín hiệu tồn tại trong một khoảng thời gian; được dùng kích hoạt và đo phản hồi. |
| 99 | `d = (v × t) / 2` | Công thức khoảng cách theo thời gian truyền âm | `d` là khoảng cách, `v` là vận tốc âm, `t` là thời gian đi-về; chia 2 vì đường truyền hai chiều. |
| 100 | Ngưỡng khoảng cách / vật cản | Giá trị quyết định / vật nằm trên hướng di chuyển | Phần mềm so sánh khoảng cách với ngưỡng để chọn phản ứng. |
| 101 | Servo / SG90 | Cơ cấu điều khiển vị trí góc / mẫu servo sử dụng | Quay cảm biến sang các hướng mà không cần xoay toàn bộ xe. |
| 102 | Phản hồi vị trí / bộ truyền bánh răng | Cơ chế kiểm tra vị trí / truyền chuyển động của servo | Giúp servo đưa trục đến góc đặt trong khả năng của nó. |
| 103 | `SERVO_SIG` | Tên mạng tín hiệu điều khiển servo | Nối GPIO13 đến đầu nhận xung của SG90. |
| 104 | Relay / rơ-le / tiếp điểm | Thiết bị đóng ngắt mạch bằng tiếp điểm | Tách việc cho phép cấp nguồn motor khỏi tín hiệu chọn chiều quay. |
| 105 | IN / `RELAY_IN` | Đầu vào relay / tên mạng điều khiển relay | Đường tín hiệu từ GPIO26 đến module relay. |
| 106 | COM | Common — tiếp điểm chung | Nhận nguồn phía tải; không đồng nghĩa chân VCC nuôi mạch điều khiển. |
| 107 | NO | Normally Open — tiếp điểm thường mở | Hở với COM khi relay chưa kích; dùng cấp nguồn motor khi đóng. |
| 108 | NC | Normally Closed — tiếp điểm thường đóng | Nối COM khi relay chưa kích; chân này không được sử dụng trong mạch. |
| 109 | Active LOW / kích mức thấp | Tín hiệu điều khiển có hiệu lực khi LOW | Đặc tính phụ thuộc module; tài liệu phần cứng yêu cầu xác minh trên relay thật. |
| 110 | Buzzer / BZ1 / buzzer chủ động | Bộ phát âm cảnh báo / ký hiệu buzzer / loại tự tạo dao động âm | Theo giả định linh kiện tương thích, cấp tín hiệu thích hợp sẽ phát âm. |
| 111 | `BUZZER_CTRL` | Tên mạng điều khiển buzzer | Đường từ GPIO12 đến buzzer. |
| 112 | LED / D1 | Light-Emitting Diode — diode phát sáng / ký hiệu LED | Báo sự hiện diện của nguồn tại vị trí mắc, không xác nhận toàn hệ thống hoạt động tốt. |
| 113 | Anode / A; Cathode / K | Cực anốt; cực catốt của diode | Hai cực LED; A ở đây là ký hiệu anode, khác A dùng cho đơn vị ampere. |
| 114 | Điện áp thuận | Forward voltage | Điện áp trên LED khi dẫn thuận; dùng khi tính dòng qua điện trở hạn dòng. |
| 115 | V / W | Volt / watt | Đơn vị điện áp / công suất. |
| 116 | A / mA | Ampere / milliampere | Đơn vị dòng điện; 1 A = 1.000 mA. |
| 117 | Ω / kΩ | Ohm / kiloohm | Đơn vị điện trở; 1 kΩ = 1.000 Ω. |
| 118 | kHz | Kilohertz | 1.000 chu kỳ mỗi giây; HC-SR04 được mô tả có sóng khoảng 40 kHz. |
| 119 | µs / cm / ° | Microgiây / centimét / độ góc | Các đơn vị dùng cho thời gian xung, khoảng cách và góc servo. |
| 120 | Chế độ thủ công / tự động tránh vật cản | Manual / autonomous obstacle avoidance | Người dùng quyết định chuyển động hoặc chương trình quyết định từ dữ liệu cảm biến. |

## 2. Bảng thuật ngữ trong WebArchitecture.md

| STT | Thuật ngữ / ký hiệu | Tên đầy đủ hoặc nghĩa tiếng Việt | Diễn giải trong hệ thống |
| --- | --- | --- | --- |
| 1 | SmartRobot | Tên hệ thống robot | Gồm ứng dụng web, backend, database và các xe chạy firmware ESP32. |
| 2 | Website / web app / app | Trang web / ứng dụng web / ứng dụng | Giao diện quản lý, điều khiển và theo dõi xe qua trình duyệt. |
| 3 | Browser / trình duyệt | Phần mềm chạy ứng dụng web | Tải frontend và kết nối API/WebSocket của backend. |
| 4 | Frontend / FE | Phần giao diện phía người dùng | Ứng dụng React hiển thị xe và chuyển thao tác thành request. |
| 5 | Backend / BE / server | Phần xử lý phía máy chủ / máy chủ | FastAPI xác thực, quản lý lượt mượn, giao lệnh và nhận báo cáo. |
| 6 | Client / HTTP(S) client | Phía chủ động gửi yêu cầu | Trình duyệt và ESP32 đều đóng vai trò client của backend. |
| 7 | Database / DB / PostgreSQL | Cơ sở dữ liệu / hệ quản trị PostgreSQL | Lưu dữ liệu tài khoản, xe, lượt mượn, lệnh và telemetry. |
| 8 | Firmware | Chương trình chạy trên vi điều khiển | Đọc cảm biến, nhận lệnh và điều khiển output trên ESP32. |
| 9 | Source / mã nguồn / repository | Mã chương trình / kho mã dự án | Nơi chứa frontend, backend, firmware và tài liệu để đối chiếu. |
| 10 | Kiến trúc phân tầng | Phân chia trách nhiệm giữa các phần hệ thống | Web nhận thao tác; backend quản lý quyền; firmware xử lý phần cứng; database lưu trạng thái. |
| 11 | React / React DOM | Thư viện giao diện / phần tích hợp React với DOM | Xây dựng và cập nhật giao diện theo trạng thái ứng dụng. |
| 12 | DOM | Document Object Model — mô hình đối tượng tài liệu | Cấu trúc biểu diễn trang web để chương trình thao tác. |
| 13 | Component | Thành phần giao diện tái sử dụng | Các khối như D-Pad, chọn mode, trạng thái xe và hộp thoại. |
| 14 | TypeScript / types | Ngôn ngữ bổ sung hệ thống kiểu cho JavaScript / các kiểu dữ liệu | Mô tả cấu trúc user, xe, lệnh và telemetry ở frontend. |
| 15 | JavaScript | Ngôn ngữ lập trình chạy ở trình duyệt | Thực hiện logic giao diện và gọi API. |
| 16 | HTML | HyperText Markup Language | Ngôn ngữ đánh dấu cấu trúc trang web. |
| 17 | CSS | Cascading Style Sheets | Ngôn ngữ định dạng hình thức và bố cục giao diện. |
| 18 | Vite | Công cụ phát triển và build frontend | Cấp dev server, proxy API/WebSocket và tạo bản build. |
| 19 | React Router DOM / router | Thư viện điều hướng / bộ định tuyến | Chuyển trang trong ứng dụng theo URL mà không tải lại toàn bộ ứng dụng. |
| 20 | Route / routes | Tuyến xử lý hoặc đường dẫn ứng dụng | Ở frontend là trang; ở backend là hàm xử lý request khớp đường dẫn/phương thức. |
| 21 | ProtectedRoute / AdminRoute | Các thành phần bảo vệ route trong dự án | Yêu cầu đăng nhập hoặc role ADMIN trước khi hiển thị trang. |
| 22 | TanStack React Query / React Query | Thư viện quản lý dữ liệu từ server | Truy vấn, cache và cập nhật danh sách, chi tiết, trạng thái xe. |
| 23 | Query / truy vấn | Yêu cầu đọc dữ liệu | Có thể là truy vấn API ở frontend hoặc truy vấn database ở backend. |
| 24 | Query cache / cache | Bộ nhớ đệm dữ liệu | Lưu kết quả truy vấn để tái sử dụng; lease secret không được đặt trong Query cache. |
| 25 | Tailwind CSS | Framework CSS theo lớp tiện ích | Dùng tạo kiểu dáng giao diện. |
| 26 | Lucide React | Bộ biểu tượng dùng trong React | Cung cấp icon cho các thành phần giao diện. |
| 27 | Vitest | Công cụ chạy kiểm thử JavaScript/TypeScript | Kiểm tra logic frontend và tương tác trong môi trường test. |
| 28 | Testing Library | Bộ thư viện kiểm thử giao diện | Hỗ trợ kiểm tra component theo thao tác người dùng. |
| 29 | jsdom | Môi trường mô phỏng DOM bằng JavaScript | Cho phép kiểm thử giao diện trong môi trường không phải trình duyệt đầy đủ. |
| 30 | Hook / hooks | Cơ chế quản lý trạng thái và vòng đời trong React | Các hook dự án phối hợp truy vấn xe và điều khiển. |
| 31 | Context / AuthProvider | Cơ chế chia sẻ dữ liệu React / thành phần cung cấp trạng thái xác thực | Cho các trang và component cùng sử dụng thông tin đăng nhập. |
| 32 | Layout / page | Bố cục chung / màn hình ứng dụng | Tổ chức giao diện người dùng, quản trị và điều khiển xe. |
| 33 | Service | Lớp xử lý chuyên trách | Ở frontend bao gói giao tiếp; ở backend thực hiện quy tắc nghiệp vụ. |
| 34 | State | Trạng thái hiện tại | Có thể là state React, trạng thái điều khiển trong DB hoặc trạng thái firmware. |
| 35 | Render | Tạo/cập nhật phần hiển thị | React dựng giao diện theo dữ liệu và trạng thái mới. |
| 36 | SPA / ứng dụng một trang | Single-Page Application | Ứng dụng tải giao diện chính một lần rồi điều hướng phía client. |
| 37 | Dashboard | Trang tổng quan | Liệt kê xe và các trạng thái để người dùng chọn xem/điều khiển. |
| 38 | UI | User Interface — giao diện người dùng | Các màn hình, nút và chỉ báo trên website. |
| 39 | D-Pad | Directional Pad — cụm điều khiển hướng | Bốn hướng tiến, lùi, trái, phải; giữ để điều khiển Manual. |
| 40 | WASD / phím mũi tên | Nhóm phím điều hướng | Đầu vào bàn phím tương ứng các hướng điều khiển xe. |
| 41 | Blur / tab ẩn / cancel | Mất focus / trang không hiển thị / hủy thao tác | Các tình huống khiến frontend ngừng ý định Manual đang giữ. |
| 42 | Python | Ngôn ngữ lập trình backend | Dùng xây dựng FastAPI và các công cụ hỗ trợ. |
| 43 | FastAPI | Framework xây dựng API Python | Định nghĩa REST API, WebSocket, dependency và schema vào/ra. |
| 44 | Uvicorn | Máy chủ ứng dụng ASGI | Chạy backend FastAPI và tiếp nhận kết nối HTTP/WebSocket. |
| 45 | ASGI | Asynchronous Server Gateway Interface | Giao diện giữa máy chủ Python và ứng dụng hỗ trợ các kết nối như HTTP/WebSocket. |
| 46 | Pydantic | Thư viện kiểm tra và định kiểu dữ liệu | Kiểm tra payload và tạo schema request/response. |
| 47 | Pydantic Settings | Thành phần quản lý cấu hình của Pydantic | Đọc biến môi trường và file cấu hình cho backend. |
| 48 | SQL | Structured Query Language — ngôn ngữ truy vấn có cấu trúc | Đọc và cập nhật dữ liệu trong PostgreSQL. |
| 49 | SQLAlchemy | Thư viện truy cập database và ORM Python | Quản lý model, truy vấn, transaction và session DB. |
| 50 | ORM | Object-Relational Mapping — ánh xạ đối tượng–quan hệ | Ánh xạ đối tượng Python tới bảng và bản ghi trong database. |
| 51 | Model | Mô hình dữ liệu | Trong backend là các lớp biểu diễn dữ liệu lưu trữ. |
| 52 | Psycopg / driver | Thư viện kết nối PostgreSQL / lớp giao tiếp | Chuyển yêu cầu của ứng dụng tới PostgreSQL. |
| 53 | Repository | Lớp truy cập dữ liệu | Tập trung các thao tác đọc/ghi cho một nhóm nghiệp vụ. |
| 54 | Schema | Cấu trúc và quy tắc dữ liệu | Có thể chỉ cấu trúc DB hoặc hợp đồng kiểm tra payload. |
| 55 | Alembic / migration / revision | Công cụ / thay đổi schema / định danh một bước thay đổi | Nâng cấp cấu trúc DB theo lịch sử; `0005_persistent_borrow` là revision được tài liệu nhắc tới. |
| 56 | Transaction | Giao dịch database | Nhóm thao tác cần thành công hoặc thất bại cùng nhau để bảo đảm nhất quán. |
| 57 | Row lock / khóa dòng | Khóa bản ghi trong transaction | Tuần tự hóa việc nhận xe và cập nhật quyền/lệnh trên cùng robot. |
| 58 | Unique / ràng buộc duy nhất | Quy tắc ngăn dữ liệu trùng theo khóa | Cùng với khóa dòng bảo đảm mỗi xe chỉ có một lượt mượn mở. |
| 59 | Engine / session factory / DB session | Bộ quản lý kết nối / bộ tạo session / phiên làm việc với DB | Được backend khởi tạo và sử dụng để truy vấn theo vòng đời ứng dụng/request. |
| 60 | Dependency | Thư viện phụ thuộc hoặc thành phần được cung cấp cho hàm xử lý | Trong manifest là gói cần cài; trong FastAPI có thể cấp config, DB session hoặc danh tính. |
| 61 | Docker Compose | Công cụ định nghĩa và chạy các dịch vụ container | Trong dự án dùng khởi tạo PostgreSQL. |
| 62 | Volume | Vùng lưu trữ bền vững cho container | Giữ dữ liệu PostgreSQL tách khỏi vòng đời container. |
| 63 | uv | Công cụ quản lý dự án và môi trường Python | Cài dependency và chạy lệnh trong môi trường backend. |
| 64 | pytest | Framework kiểm thử Python | Chạy kiểm thử backend. |
| 65 | Ruff | Công cụ kiểm tra và định dạng mã Python | Hỗ trợ kiểm tra chất lượng, quy tắc và định dạng mã. |
| 66 | Manifest / lockfile | File khai báo dependency / file khóa phiên bản | Manifest nêu yêu cầu; lockfile chốt bộ phiên bản phục vụ cài đặt tái lập. |
| 67 | `^` / `~` trong phiên bản | Các toán tử phạm vi phiên bản dependency | Thể hiện phạm vi bản được chấp nhận theo quy tắc công cụ, không phải số bản đã cài chính xác. |
| 68 | API | Application Programming Interface — giao diện lập trình ứng dụng | Hợp đồng để trình duyệt và ESP32 giao tiếp với backend. |
| 69 | REST / REST API | Representational State Transfer | Phong cách tổ chức giao tiếp tài nguyên; dùng cho đăng nhập, quản lý và lệnh điều khiển. |
| 70 | OpenAPI | Chuẩn mô tả API | Mô tả endpoint, payload và response của backend. |
| 71 | Endpoint | Điểm truy cập một chức năng API | Một đường dẫn kết hợp phương thức HTTP, ví dụ POST nhận quyền điều khiển. |
| 72 | HTTP / HTTPS / HTTP(S) | Hypertext Transfer Protocol / HTTP qua TLS / cách viết chung | Giao thức trao đổi request/response; HTTPS bảo vệ đường truyền bằng mã hóa. |
| 73 | GET / POST | Hai phương thức HTTP | GET chủ yếu đọc dữ liệu; POST gửi dữ liệu hoặc thực hiện thao tác. |
| 74 | Request / response | Yêu cầu / phản hồi | Một bên gửi yêu cầu, backend trả dữ liệu hoặc kết quả xử lý. |
| 75 | Header / body / payload | Metadata HTTP / phần thân / dữ liệu mang theo | Header mang token, body thường chứa dữ liệu JSON của thao tác. |
| 76 | JSON / cJSON | JavaScript Object Notation / thư viện xử lý JSON bằng C | Định dạng dữ liệu trao đổi; cJSON dùng trong firmware. |
| 77 | `fetch` | API HTTP của môi trường JavaScript | Frontend dùng để gửi request tới backend. |
| 78 | URL | Uniform Resource Locator — địa chỉ tài nguyên | Xác định địa chỉ web hoặc backend mà trình duyệt/ESP32 truy cập. |
| 79 | ID / UUID | Định danh / Universally Unique Identifier | Nhận diện user, robot, phiên, lệnh và thao tác. |
| 80 | WebSocket / WS / WSS | Kết nối hai chiều duy trì liên tục / tên viết tắt / WebSocket qua TLS | Backend gửi snapshot tới trình duyệt; lệnh điều khiển vẫn qua REST. |
| 81 | Socket / connection | Điểm cuối giao tiếp / kết nối | Ngữ cảnh tài liệu chủ yếu chỉ kết nối WebSocket của trang điều khiển. |
| 82 | Frame | Đơn vị dữ liệu của WebSocket | Frame đầu mang thông tin xác thực; các bản tin sau mang state hoặc ping. |
| 83 | WebSocket Upgrade | Chuyển giao tiếp HTTP sang WebSocket | Reverse proxy cần hỗ trợ để kênh trạng thái hoạt động. |
| 84 | Snapshot / `robot.state` | Ảnh chụp trạng thái / loại bản tin state của dự án | Backend đọc DB định kỳ rồi gửi trạng thái hiện tại. |
| 85 | `ping` | Bản tin kiểm tra duy trì kết nối | Trong dự án là bản tin ứng dụng khi không có state thay đổi; giúp frontend phát hiện mất phản hồi. |
| 86 | Realtime | Cập nhật gần thời gian thực | Có độ trễ theo chu kỳ đọc/gửi và mạng; không phải bảo đảm thời gian thực cứng. |
| 87 | Poll / polling | Chủ động hỏi dữ liệu lặp lại | ESP32 lấy lệnh hiện hành; frontend cũng có polling dữ liệu xe/fallback. |
| 88 | Heartbeat | Bản tin báo thiết bị còn liên lạc | Backend dựa trên heartbeat hợp lệ để tính Online/Offline. |
| 89 | Telemetry | Dữ liệu đo và trạng thái được gửi từ thiết bị | Gồm khoảng cách, vật cản, mode, output chuyển động và buzzer. |
| 90 | Freshness / telemetry freshness | Độ mới của dữ liệu | Dữ liệu cũ không được hiển thị như báo cáo mới. |
| 91 | MQTT | Message Queuing Telemetry Transport | Giao thức publish/subscribe được nhắc đến để xác định dự án hiện không dùng. |
| 92 | Broker | Máy chủ trung gian phân phối thông điệp | Không có broker MQTT trong đường điều khiển hiện tại. |
| 93 | Auth / authentication / authenticate | Xác thực / thao tác xác thực | Kiểm tra danh tính người dùng hoặc thiết bị trước khi cấp quyền. |
| 94 | Authorization / phân quyền | Kiểm tra quyền thực hiện thao tác | Phân biệt đã biết danh tính với có quyền điều khiển một xe cụ thể. |
| 95 | USER / ADMIN / role | Người dùng / quản trị viên / vai trò | ADMIN có chức năng quản trị; không tự chiếm lượt mượn xe của người khác qua acquire. |
| 96 | Active / vô hiệu hóa | Đang được cho phép sử dụng / ngừng cho phép | Trạng thái tài khoản/xe ảnh hưởng quyền truy cập và điều khiển. |
| 97 | Login / logout | Đăng nhập / đăng xuất | Tạo hoặc thu hồi phiên người dùng; logout không tự đóng lượt mượn trong thiết kế hiện tại. |
| 98 | Auth session / session / device session | Phiên đăng nhập / phiên làm việc / phiên thiết bị | Ba ngữ cảnh khác nhau; không đồng nhất với lượt mượn hay DB session. |
| 99 | JWT | JSON Web Token | Định dạng access token dùng để mang các thông tin xác thực có chữ ký. |
| 100 | PyJWT / HS256 | Thư viện JWT Python / HMAC-SHA-256 | Công cụ và thuật toán ký/kiểm tra access token của backend. |
| 101 | Access token | Token truy cập | Frontend giữ trong bộ nhớ để gọi API và xác thực WebSocket. |
| 102 | Refresh token / refresh / xoay token | Token làm mới / cấp lại access token / thay token cũ | Duy trì phiên qua cookie và giảm việc đăng nhập lại. |
| 103 | Cookie / HttpOnly / secure cookie | Dữ liệu trình duyệt gửi kèm / thuộc tính chặn JavaScript đọc / cookie chỉ gửi qua HTTPS | Bảo vệ và vận chuyển thông tin phiên theo cấu hình. |
| 104 | CSRF / `X-CSRF-Token` | Cross-Site Request Forgery / header mang token chống giả mạo yêu cầu | Bảo vệ các thao tác dùng cookie nhạy cảm. |
| 105 | Origin | Nguồn của trang, gồm scheme, hostname và port | Backend đối chiếu nguồn gọi request hoặc mở WebSocket. |
| 106 | CORS | Cross-Origin Resource Sharing | Cơ chế kiểm soát truy cập tài nguyên khác origin từ trình duyệt. |
| 107 | Web Locks | API khóa phối hợp giữa các ngữ cảnh cùng origin | Frontend dùng khi được hỗ trợ để tuần tự hóa xoay cookie giữa các tab. |
| 108 | localStorage / browser storage | Bộ nhớ lưu trữ phía trình duyệt | Access token và lease secret không được lưu bền vững ở đây trong thiết kế hiện tại. |
| 109 | RAM / bộ nhớ JavaScript | Random-Access Memory / bộ nhớ lúc chương trình chạy | Lưu tạm token và trạng thái; không thay thế lưu trữ bền vững của DB. |
| 110 | Credential / secret / token | Thông tin xác thực / bí mật / chuỗi đại diện quyền hoặc phiên | Phải phân biệt credential thiết bị, JWT người dùng và lease token. |
| 111 | Device ID / Device Secret | Định danh / bí mật riêng của thiết bị | Cho phép backend xác thực đúng xe; không dùng JWT người dùng để giả làm xe. |
| 112 | `X-Device-ID` / `X-Device-Secret` | Hai header mang credential thiết bị | ESP32 gửi khi gọi Device API. |
| 113 | `X-Device-Session` / `device_session_id` | Header phiên / trường định danh phiên thiết bị | Gắn request với phiên do backend cấp sau authenticate. |
| 114 | Hash / băm / credential hash | Giá trị một chiều tạo từ dữ liệu / hash thông tin xác thực | Database lưu các hash thích hợp thay vì secret thô. |
| 115 | Argon2-cffi / Argon2id | Thư viện Argon2 Python / biến thể thuật toán băm mật khẩu | Dùng bảo vệ mật khẩu người dùng; không phải thuật toán ký JWT. |
| 116 | Chứng chỉ / mã hóa | Thông tin xác minh danh tính TLS / bảo vệ dữ liệu bằng mật mã | HTTPS cần kiểm tra chứng chỉ; firmware đồng bộ giờ để kiểm tra hợp lệ. |
| 117 | Binding | Ràng buộc giữa các danh tính/phiên | Lượt mượn được gắn với người dùng và phiên đăng nhập phù hợp. |
| 118 | Lease / lượt mượn | Quyền sở hữu điều khiển độc quyền một xe | Hiện giữ đến khi trả xe hoặc bị thu hồi quản trị, không tự hết chỉ vì mất mạng. |
| 119 | Lease ID / `control_session_id` | Định danh lượt mượn | Xác định lượt mượn trong body request điều khiển. |
| 120 | Lease secret / lease token / `lease_token` | Bí mật của lượt mượn | Frontend giữ trong bộ nhớ và gửi kèm thao tác cần quyền điều khiển. |
| 121 | Acquire / nhận điều khiển | Xin cấp hoặc khôi phục quyền mượn xe | Backend kiểm tra chủ sở hữu và yêu cầu handoff Manual an toàn. |
| 122 | Renew / duy trì quyền | Cập nhật quyền điều khiển/permit theo chu kỳ | Duy trì Auto permit và khôi phục handoff khi phù hợp; không biến lượt mượn thành lệnh vô hạn. |
| 123 | Release / trả xe | Đóng lượt mượn | Khi thiết bị nhận trạng thái mới, chuyển động dừng và relay bị ngắt. |
| 124 | `renew_after_ms` | Khoảng đợi trước lần renew tiếp theo | Backend trả để frontend lên lịch renew, đơn vị mili giây. |
| 125 | `expires_at` | Thời điểm hết hiệu lực | Ở lượt mượn hiện tại có thể null; lệnh chuyển động vẫn có TTL hữu hạn. |
| 126 | `null` / `true` | Không có giá trị / giá trị logic đúng | `expires_at=null` không đồng nghĩa mọi loại quyền đều vô hạn; `true` biểu diễn cờ được bật. |
| 127 | Command / lệnh / command ID | Yêu cầu điều khiển / định danh lệnh | Lệnh lưu trong DB rồi được giao cho ESP32 theo điều kiện hiệu lực. |
| 128 | `request_id` | Định danh duy nhất của thao tác phía client | Retry cùng key và nội dung không tạo thêm lệnh mới. |
| 129 | `client_sequence` | Số thứ tự do frontend cấp trong lượt mượn | Chặn request mới có thứ tự cũ hoặc trùng không hợp lệ. |
| 130 | `sequence` | Bộ đếm thứ tự lệnh do backend cấp theo xe | Lưu bền vững, không đặt lại khi dọn lịch sử. |
| 131 | `generation` | Thế hệ điều khiển | Tăng để vô hiệu hóa lệnh thuộc thế hệ cũ sau STOP, acquire, đổi mode hoặc đóng quyền. |
| 132 | Key / retry key | Khóa nhận diện một thao tác | Trong luồng chống trùng chủ yếu là request ID được giữ nguyên khi retry. |
| 133 | Retry | Thử gửi lại thao tác | Không được tự làm mới hiệu lực của lệnh cũ hoặc tạo ý định trùng ngoài ý muốn. |
| 134 | TTL | Time To Live — khoảng thời gian có hiệu lực | Giới hạn tuổi lệnh MOVE/STOP, MODE và permit. |
| 135 | Deadline | Mốc thời gian hết hiệu lực | Firmware phải dừng khi vượt mốc, kể cả request đang chậm hoặc retry. |
| 136 | Fence / vô hiệu hóa lệnh cũ | Cơ chế chặn tác động của thế hệ/quyền điều khiển cũ | Ngăn request hoặc báo cáo chậm làm sống lại chuyển động đã bị thay thế. |
| 137 | Hàng đợi / tuần tự hóa request | Tập thao tác chờ / xử lý theo thứ tự | Frontend tuần tự hóa request nhưng loại bỏ ý định MOVE cũ khi cần dừng. |
| 138 | Intent | Ý định điều khiển hiện hành | Ví dụ người dùng đang giữ nút tiến; không đồng nghĩa lệnh đã được áp dụng. |
| 139 | ACK | Acknowledgement — xác nhận lệnh | Firmware báo đã nhận, áp dụng, từ chối hoặc thất bại. |
| 140 | Receipt | Phản hồi ghi nhận việc nhận dữ liệu | Backend trả cho ACK/telemetry; không phải bằng chứng chuyển động vật lý. |
| 141 | ACCEPTED / HTTP 202 | Đã tiếp nhận yêu cầu | Backend đã lưu lệnh; chưa chứng minh firmware đã nhận hoặc xe đã chạy. |
| 142 | RECEIVED | Đã nhận lệnh | Firmware xác nhận tiếp nhận lệnh. |
| 143 | APPLIED | Đã chấp nhận áp dụng lệnh | Xác nhận phía firmware; không chứng minh bánh đã quay. |
| 144 | REJECTED | Lệnh bị từ chối | Không được áp dụng theo điều kiện xử lý của thiết bị/giao thức. |
| 145 | FAILED | Xử lý lệnh thất bại | Ghi nhận không hoàn tất việc áp dụng lệnh. |
| 146 | SUPERSEDED | Lệnh bị thay thế | Lệnh mới hoặc fence đã làm lệnh trước mất quyền thực thi. |
| 147 | EXPIRED | Lệnh hết hạn | TTL đã hết, không còn được thực thi. |
| 148 | HTTP 401 | Unauthorized — thiếu hoặc không hợp lệ về xác thực | Frontend có thể thử refresh rồi gọi lại request. |
| 149 | HTTP 403 / trang `/403` | Forbidden — không được phép truy cập | Tài liệu dùng đường dẫn này cho màn hình thiếu quyền. |
| 150 | Manual / MANUAL | Chế độ điều khiển thủ công | Xe nhận MOVE từ thao tác giữ D-Pad/phím sau khi mode được xác nhận. |
| 151 | Auto / AUTO | Chế độ tự động | ESP32 tự chọn chuyển động theo cảm biến trong phạm vi permit hợp lệ. |
| 152 | Mode / `mode` / MODE | Chế độ / trường mode / loại lệnh chuyển mode | Cùng từ nhưng dùng để chỉ trạng thái vận hành hoặc lệnh thiết lập trạng thái đó. |
| 153 | Pending | Đang chờ xác nhận | Giao diện khóa điều khiển trong lúc handoff mode chưa hoàn tất. |
| 154 | Handoff / safe mode switch | Bàn giao chế độ / chuyển chế độ an toàn | Firmware dừng chuyển động trước khi xác nhận mode mới. |
| 155 | `safe_mode_switch` | Cờ xác nhận chuyển mode an toàn | Phải đi cùng ACK APPLIED, actual mode phù hợp và actual movement STOPPED. |
| 156 | `actual_mode` | Mode thực tế do firmware báo cáo | Phân biệt với lựa chọn/yêu cầu mode của người dùng. |
| 157 | `actual_movement` | Trạng thái chuyển động/output do firmware báo cáo | Không phải phép đo vận tốc hoặc hành trình bằng encoder. |
| 158 | MOVE / STOP / STOPPED | Lệnh di chuyển / lệnh dừng / trạng thái đã dừng output | STOP là yêu cầu; STOPPED là giá trị trạng thái báo cáo. |
| 159 | FORWARD / BACKWARD / TURN_LEFT / TURN_RIGHT | Tiến / lùi / quay trái / quay phải | Các giá trị hướng được API điều khiển chấp nhận. |
| 160 | `direction` / `kind` | Hướng / loại lệnh | Firmware cần diễn giải đồng thời loại lệnh, mode và hướng, không chỉ đọc direction. |
| 161 | KEEPALIVE / Auto permit | Lệnh duy trì / quyền chạy Auto trong thời gian hữu hạn | Cho phép state machine Auto tiếp tục khi còn hiệu lực. |
| 162 | Envelope | Gói bọc giao lệnh và quyền hiện hành | Mang mode, quyền, thời hạn, thế hệ và lệnh hiện tại hoặc trạng thái không còn quyền. |
| 163 | Online / Offline / Busy | Còn liên lạc / mất liên lạc / đang được mượn khi Online | Backend suy ra từ heartbeat và lượt mượn, không phải từ LED nguồn. |
| 164 | `last_seen_at` | Thời điểm heartbeat hợp lệ gần nhất | Dùng xác định tình trạng liên lạc thiết bị. |
| 165 | Boot / boot ID / reboot / reset / startup | Khởi động / định danh lần khởi động / khởi động lại / đặt lại / giai đoạn khởi tạo | Dùng theo dõi phiên thiết bị và ngăn phát lại lệnh cũ sau gián đoạn. |
| 166 | Reload / reconnect | Tải lại trang / kết nối lại | Cần khôi phục quyền hợp lệ; không tiếp tục chuyển động bằng lệnh đã cũ. |
| 167 | Backoff | Tăng khoảng chờ giữa các lần thử lại | Giảm tần suất reconnect khi kết nối tiếp tục thất bại. |
| 168 | Timeout / watchdog | Hết thời gian chờ / cơ chế giám sát thời hạn | Phát hiện mất phản hồi hoặc điều kiện không còn hợp lệ để dừng/chặn chuyển động. |
| 169 | Fallback | Cách xử lý dự phòng | Frontend đọc state bằng REST khi socket chưa hoạt động; không tự mở quyền lái. |
| 170 | Cleanup loop / cleanup task | Vòng lặp/tác vụ dọn dẹp | Xử lý lệnh hết hạn và lịch sử theo chính sách, chạy cùng backend. |
| 171 | Lưu trữ bền vững / lịch sử / nhật ký | Dữ liệu tồn tại qua khởi động lại và ghi nhận sự kiện | Database giữ quyền, thứ tự lệnh và báo cáo; dọn lịch sử không đặt lại sequence/generation. |
| 172 | `users` | Bảng người dùng | Lưu tài khoản, mật khẩu băm, role và active. |
| 173 | `auth_sessions` / `refresh_tokens` | Bảng phiên đăng nhập / refresh token | Phục vụ duy trì, xoay và thu hồi phiên xác thực. |
| 174 | `login_rate_limits` | Bảng giới hạn đăng nhập | Theo dõi số lần thử trong chính sách chống lạm dụng đăng nhập. |
| 175 | `robots` / `robot_id` | Bảng xe / định danh xe | Phân tách dữ liệu và quyền theo từng robot. |
| 176 | `control_sessions` | Bảng lượt mượn xe | Lưu người mượn, binding phiên, secret hash và thời điểm bắt đầu/kết thúc. |
| 177 | `robot_control_states` | Bảng trạng thái điều khiển | Lưu mode, sequence/generation và dữ liệu điều khiển hiện hành. |
| 178 | `robot_commands` | Bảng lệnh | Lưu nội dung, thời hạn và trạng thái xác nhận của lệnh. |
| 179 | `device_sessions` | Bảng phiên thiết bị | Liên kết xe với phiên giao tiếp và boot ID. |
| 180 | `robot_telemetry` | Bảng dữ liệu thiết bị báo về | Lưu các mẫu telemetry theo xe và phiên. |
| 181 | `audit_logs` | Bảng nhật ký nghiệp vụ/quản trị | Theo dõi sự kiện liên quan tới quản lý hệ thống. |
| 182 | `sample_sequence` | Số thứ tự mẫu telemetry | Phát hiện mẫu trùng/cũ trong phiên thiết bị; mẫu trùng không làm mới freshness. |
| 183 | `distance_cm` | Trường khoảng cách tính bằng centimét | Có thể null khi chưa có số đo hợp lệ; không diễn giải null thành đường trống. |
| 184 | `telemetry_fresh` | Cờ thể hiện telemetry còn mới | UI dùng để tránh trình bày dữ liệu cũ như trạng thái hiện hành. |
| 185 | SENSOR_ERROR | Trạng thái lỗi/không có mẫu cảm biến hợp lệ | Chặn suy diễn phía trước thông thoáng từ dữ liệu thiếu hoặc lỗi. |
| 186 | ESP32 / ESP32 DevKit V1 / `esp32dev` | Vi điều khiển / bo phát triển / tên target PlatformIO | Nút điều khiển phần cứng và giao tiếp backend. |
| 187 | C | Ngôn ngữ lập trình C | Ngôn ngữ dùng viết firmware hiện tại. |
| 188 | ESP-IDF | Espressif IoT Development Framework | Framework cung cấp các thành phần hệ thống và driver cho ESP32. |
| 189 | FreeRTOS | Free Real-Time Operating System | Hệ điều hành thời gian thực dùng lập lịch các task firmware. |
| 190 | PlatformIO / platform / board / `espressif32` | Công cụ build / gói nền tảng / bo mục tiêu / nền tảng Espressif 32-bit | Xác định môi trường build firmware ESP-IDF cho ESP32. |
| 191 | Task / control task / safety task / sensor task / task HTTP | Tác vụ / các tác vụ điều khiển, giám sát, cảm biến, giao tiếp | Tách xử lý cục bộ khỏi độ trễ request mạng. |
| 192 | Tick / chu kỳ / lập lịch | Lần xử lý định kỳ / khoảng lặp / phân bổ thực thi | Control tick và safety tick là mục tiêu phần mềm, không bảo đảm thời gian dừng cơ khí. |
| 193 | State machine | Máy trạng thái | Tổ chức Manual/Auto thành các trạng thái và chuyển trạng thái có điều kiện. |
| 194 | Output / motor | Đầu ra điều khiển / động cơ | Output phản ánh tín hiệu firmware đang phát, không tự chứng minh chuyển động vật lý. |
| 195 | GPIO | General-Purpose Input/Output | Đọc ECHO và điều khiển L298N, servo, relay, buzzer. |
| 196 | GPIO19 / GPIO21 / GPIO5 / GPIO18 | Nhóm GPIO điều khiển motor | Lần lượt đến IN1/IN2/IN3/IN4 của L298N. |
| 197 | GPIO27 / GPIO14 / GPIO13 / GPIO26 / GPIO12 | GPIO TRIG / ECHO / servo / relay / buzzer | Ánh xạ phần mềm với các khối phần cứng tương ứng. |
| 198 | PWM / LEDC | Pulse Width Modulation / ngoại vi LED Control của ESP32 | LEDC tạo PWM; firmware đặt PWM motor trên IN1–IN4. |
| 199 | Duty / duty cycle / độ phân giải 8 bit | Giá trị đặt xung / tỷ lệ bật xung / 256 mức biểu diễn | Motor dùng giá trị 0–255; 75 là giá trị duty, không phải 75% hay tốc độ đo được. |
| 200 | `full` / `slow` / `turn`; `full_speed` / `slow_speed` | Mức PWM chạy thường / chậm / quay; các tên cấu hình tốc độ | Mặc định nêu trong tài liệu là 75/30/75, chịu bù PWM từng bánh. |
| 201 | Bù PWM / hệ số bù | Điều chỉnh duty riêng cho từng bánh | Giảm lệch giữa hai motor; không phải điều khiển tốc độ có phản hồi encoder. |
| 202 | NVS | Non-Volatile Storage — lưu trữ không mất khi tắt nguồn | Lưu Wi-Fi, backend URL, credential và tham số vận hành của xe. |
| 203 | Flash / app image / provisioning | Bộ nhớ flash / ảnh nhị phân ứng dụng / cấp cấu hình thiết bị | Credential nằm trong cấu hình NVS, không nhúng vào app image; NVS hiện chưa mã hóa. |
| 204 | OTA | Over-The-Air update — cập nhật qua mạng | Firmware hiện chưa triển khai tính năng này. |
| 205 | L298N / cầu H | Module driver hai động cơ / mạch đảo chiều điện áp | Chuyển PWM/GPIO của ESP32 thành điều khiển công suất motor. |
| 206 | IN1 / IN2 / IN3 / IN4; OUT1 / OUT2 / OUT3 / OUT4 | Bốn đầu vào / bốn đầu ra của L298N | IN1/IN2 và OUT1/OUT2 ứng với bánh phải; cặp còn lại ứng với bánh trái. |
| 207 | ENA / ENB / jumper enable | Chân cho phép kênh A/B / cầu nối cho phép kênh | Không có GPIO ENA/ENB trong firmware; cần lắp jumper phù hợp. |
| 208 | HC-SR04 / sensor / TRIG / ECHO | Cảm biến siêu âm / cảm biến / kích hoạt / phản hồi | Đo khoảng cách bằng thời gian truyền âm đi-về. |
| 209 | Ngắt / cạnh lên / cạnh xuống | Interrupt / chuyển LOW→HIGH / chuyển HIGH→LOW | Firmware ghi thời điểm các cạnh ECHO để tính độ rộng xung. |
| 210 | `echo_width_us` | Độ rộng xung ECHO tính bằng microgiây | Dùng trong công thức `distance_cm = echo_width_us × 0,0343 / 2`. |
| 211 | Mẫu hợp lệ / mẫu cũ / mẫu trùng | Số đo đạt kiểm tra / quá tuổi / đã nhận trước đó | Được xử lý khác nhau; không mẫu nào tự động đồng nghĩa phía trước an toàn. |
| 212 | Servo / SG90 / góc giữa | Cơ cấu định vị góc / mẫu servo / hướng nhìn phía trước | Quét trái 0°, giữa 90°, phải 180° theo cấu hình hiện tại. |
| 213 | Heuristic kẹt | Quy tắc ước đoán xe bị kẹt | Dựa trên biến thiên khoảng cách, không phải số đo bánh bị khóa. |
| 214 | Encoder | Cảm biến mã hóa chuyển động quay | Hệ thống hiện chưa có để đo tốc độ bánh hoặc xác nhận quãng đường thực tế. |
| 215 | Relay / active-low / LOW / HIGH | Rơ-le / kích mức thấp / mức thấp / mức cao | Với cấu hình hiện tại, LOW bật relay nguồn motor; HIGH tắt. |
| 216 | `motors_enabled` | Cờ cho phép vận hành motor | Phải bật và đủ điều kiện runtime thì mới có thể cấp nguồn/PWM motor. |
| 217 | `allow_blind_manual` / đợt mù | Cờ cho phép lùi/quay Manual khi không quan sát trực tiếp phía đó / đợt điều khiển giới hạn | Cho phép có điều kiện và thời gian hữu hạn; giữ nút không kéo dài vô hạn. |
| 218 | Buzzer / active-high | Còi cảnh báo / kích mức cao | Firmware điều khiển cảnh báo, web chỉ hiển thị báo cáo. |
| 219 | LED / D1 / R1 | Diode phát sáng / ký hiệu LED / điện trở hạn dòng | Đèn nguồn hoạt động theo mạch; không phải chỉ báo kết nối backend. |
| 220 | SW1 / Buck / R2 / VIN | Công tắc nguồn / bộ giảm áp / điện trở nối tiếp / chân nguồn vào | Các phần trên đường cấp nguồn; R2 không được coi là mạch ổn áp. |
| 221 | GND / DC / `BAT_PROTECTED+` / BMS | Mass chung / điện một chiều / nhãn dương pin / hệ thống quản lý pin | Các khái niệm điện cần đối chiếu bản vẽ và phần cứng thật. |
| 222 | Quán tính / thời gian dừng vật lý | Xu hướng duy trì chuyển động / thời gian xe dừng thực tế | Phụ thuộc cơ khí, tải và mặt đường; không suy ra trực tiếp từ tick/watchdog. |
| 223 | Wi-Fi / LAN | Mạng không dây / Local Area Network — mạng cục bộ | Xe và backend có thể liên lạc trong mạng nội bộ nếu định tuyến/firewall cho phép. |
| 224 | IP / IP LAN | Internet Protocol / địa chỉ IP nội bộ | Địa chỉ máy chủ mà ESP32 phải truy cập khi backend chạy trong LAN. |
| 225 | `localhost` / `127.0.0.1` | Tên máy cục bộ / địa chỉ loopback | Luôn trỏ về chính thiết bị đang dùng địa chỉ đó, không tự trỏ từ ESP32 tới máy backend. |
| 226 | Bind / port | Gắn dịch vụ với giao diện mạng / cổng giao tiếp | Backend phải lắng nghe ở giao diện mà các thiết bị cần dùng có thể truy cập. |
| 227 | Proxy / reverse proxy | Thành phần chuyển tiếp / máy chủ nhận rồi chuyển tiếp tới backend | Vite proxy phục vụ phát triển; triển khai cần cấu hình web server/reverse proxy phù hợp. |
| 228 | Web server | Máy chủ phục vụ nội dung web | Phục vụ bản build frontend và có thể chuyển tiếp API/WebSocket. |
| 229 | Build / bản build / thư mục dist | Quá trình tạo gói triển khai / kết quả build / thư mục đầu ra | Frontend cần được build và phục vụ; cấu hình dev proxy không tự đi kèm. |
| 230 | Local / development / production | Môi trường cục bộ / phát triển / triển khai vận hành | Quy tắc HTTPS, cookie và origin thay đổi theo yêu cầu môi trường. |
| 231 | SPA fallback | Trả trang ứng dụng chính khi truy cập route frontend | Giúp mở trực tiếp các đường dẫn như trang điều khiển mà không bị web server trả sai tài nguyên. |
| 232 | Health / readiness | Tình trạng tiến trình / độ sẵn sàng | Endpoint health kiểm tra ứng dụng; readiness kiểm tra kết nối database theo thiết kế. |
| 233 | `/api` / `/api/v1` | Tiền tố đường dẫn API / phiên bản API 1 | Tách các endpoint nghiệp vụ khỏi đường dẫn frontend. |
| 234 | `/login` / `/dashboard` / `/robots/:id` | Route đăng nhập / tổng quan / điều khiển một xe | `:id` là tham số định danh xe trong router frontend. |
| 235 | `/admin` / `/admin/users` / `/admin/robots` | Các route quản trị | Hiển thị tổng quan, quản lý tài khoản và quản lý xe. |
| 236 | `/auth/*` / `/admin/*` / `/devices/*` | Các nhóm endpoint xác thực / quản trị / thiết bị | Dấu `*` trong tài liệu biểu thị nhóm đường dẫn, không phải một endpoint cụ thể. |
| 237 | `/robots` / `/robots/{robot_id}` | API danh sách / chi tiết xe | Dấu ngoặc nhọn thể hiện tham số đường dẫn cần thay bằng ID thật. |
| 238 | `/robots/{robot_id}/control/*` | Nhóm endpoint điều khiển theo xe | Bao gồm acquire, renew, release, state, mode, move và stop. |
| 239 | `/ws/robots/{robot_id}` | Endpoint WebSocket theo xe | Trả snapshot trạng thái sau khi xác thực hợp lệ. |
| 240 | `/devices/authenticate` / `/devices/commands/current` | Xác thực thiết bị / lấy lệnh hiện hành | ESP32 chủ động gọi để thiết lập phiên và nhận trạng thái điều khiển mới. |
| 241 | `/devices/telemetry` / `/stop` | Gửi báo cáo thiết bị / tên nhánh dừng trong nhóm control | Phải hiểu cùng tiền tố đầy đủ; `/stop` không phải lệnh MOVE có direction STOP. |
| 242 | `/health` / `/health/ready` | Endpoint kiểm tra tiến trình / database | Nằm dưới tiền tố `/api/v1` như tài liệu mô tả. |
| 243 | Hz / kHz | Hertz / kilohertz | Chu kỳ mỗi giây; 1 kHz = 1.000 Hz. |
| 244 | ms / µs | Millisecond / microsecond — mili giây / microgiây | 1 giây = 1.000 ms = 1.000.000 µs. |
| 245 | cm / V / Ω / W / ° | Centimét / volt / ohm / watt / độ | Đơn vị khoảng cách, điện áp, điện trở, công suất và góc xuất hiện khi liên hệ phần cứng. |
| 246 | Mermaid / flowchart / sequenceDiagram | Ngôn ngữ vẽ sơ đồ / lưu đồ / sơ đồ trình tự | Dùng mô tả kiến trúc và thứ tự trao đổi giữa người dùng, web, backend, DB và ESP32. |
| 247 | Actor / participant | Tác nhân / thành phần tham gia trong sơ đồ trình tự | Actor là người dùng; participant là các thành phần trao đổi thông điệp. |
| 248 | Phase | Giai đoạn phát triển | Báo cáo của từng phase có thể mô tả hành vi đã được thay đổi trong source hiện tại. |
| 249 | Camera / định vị | Thu hình / xác định vị trí | Những khả năng được tài liệu nêu là chưa có trong website hiện tại. |

