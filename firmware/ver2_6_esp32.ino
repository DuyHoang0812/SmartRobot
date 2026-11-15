/*
 * Robot Tránh Vật Cản - ESP32 (DOIT ESP32 DEVKIT V1) + Wi-Fi Relay Control
 * (Dung sai cảm biến DIST_TOLERANCE = 5.0 cm & Kiểm tra distance < 800 cm)
 *
 * Thư viện cần cài: ESP32Servo (Library Manager)
 * WiFi.h và WebServer.h có sẵn trong gói ESP32 board package 3.x
 * Lưu ý: chân ECHO của HC-SR04 xuất 5V, ESP32 chỉ chịu 3.3V
 *        -> nên dùng cầu chia áp (vd 1k/2k) cho chân ECHO.
 */

#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>

// ---------- Cấu hình Wi-Fi & Web Server ----------
// Chế độ Access Point (ESP32 tự phát Wi-Fi, không cần router ngoài)
const char* AP_SSID = "ESP32_Robot_Control";
const char* AP_PASS = "12345678"; // Tối thiểu 8 ký tự

// Nếu muốn kết nối vào Wi-Fi nhà/trường, đổi USE_AP_MODE thành false và điền SSID/PASS bên dưới:
const bool USE_AP_MODE = true;
const char* STA_SSID = "IoT LAB";
const char* STA_PASS = "kvt1ptit";

WebServer server(80);

// ---------- Điều khiển Relay ----------
const int RELAY_PIN = 26;
const bool RELAY_ACTIVE_LOW = true; // true: kích mức THẤP (phổ biến), false: kích mức CAO
bool relayState = false;            // Trạng thái hiện tại của Relay (false = TẮT, true = BẬT)

// ---------- Mạch điều khiển động cơ (L298N) ----------
const int IN1 = 19;
const int IN2 = 21;
const int IN3 = 5;
const int IN4 = 18;

// ---------- Điều khiển tốc độ động cơ (PWM bằng LEDC của ESP32) ----------
const int PWM_FREQ = 1000;  // Tần số PWM (Hz)
const int PWM_RES  = 8;     // Độ phân giải 8 bit -> giá trị 0 - 255

int FULL_SPEED = 75;  // Tốc độ chạy bình thường
int SLOW_SPEED = 30;  // Tốc độ khi gặp cảnh báo
int TURN_SPEED = 75;  // Tốc độ khi lùi và quay xe

// ---------- Cảm biến siêu âm (HC-SR04) ----------
const int TRIG_PIN = 27;
const int ECHO_PIN = 14;
const float STOP_DISTANCE = 15.0;  // Khoảng cách dừng hẳn và quay xe (cm)
const float WARN_DISTANCE = 40.0;  // Khoảng cách giảm tốc độ & cảnh báo (cm)

// ---------- Kẹt cảm biến (Stuck Detection) ----------
float lastDistance = -1.0;
unsigned long lastDistanceChangeTime = 0;
const unsigned long STUCK_TIMEOUT_MS = 3000; // 3 giây
const float DIST_TOLERANCE = 5.0;             // Dung sai chênh lệch 5.0 cm

// ---------- Còi báo (Buzzer) ----------
const int BUZZER_PIN = 12;
bool buzzerBeepState = false;
unsigned long lastBuzzerToggle = 0;
const unsigned long BUZZER_BEEP_MS = 100;

// ---------- Động cơ Servo ----------
const int SERVO1_PIN = 13;
Servo myServo1;
const int SERVO1_CENTER = 90;

// ---------- Thời gian thực hiện chuyển hướng ----------
const unsigned long SETTLE_MS   = 600;
const unsigned long BACKUP_MS   = 400;
const unsigned long TURN_MS     = 400;

enum Direction { DIR_LEFT, DIR_RIGHT };

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(50); // parseInt() không chặn 1 giây nữa

  // Cấu hình chân Relay (tắt mặc định khi khởi động)
  pinMode(RELAY_PIN, OUTPUT);
  setRelay(false);

  // Cấu hình chân động cơ
  ledcAttach(IN1, PWM_FREQ, PWM_RES);
  ledcAttach(IN2, PWM_FREQ, PWM_RES);
  ledcAttach(IN3, PWM_FREQ, PWM_RES);
  ledcAttach(IN4, PWM_FREQ, PWM_RES);
  stopMotors();

  // Cấu hình cảm biến & còi
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  // Cấu hình Servo
  ESP32PWM::allocateTimer(3);
  myServo1.setPeriodHertz(50);
  myServo1.attach(SERVO1_PIN, 500, 2400);
  myServo1.write(SERVO1_CENTER);

  // Khởi tạo Wi-Fi và Web Server
  setupWiFi();

  Serial.println(F("System Ready."));
}

void loop() {
  // Xử lý yêu cầu HTTP từ trình duyệt (non-blocking)
  server.handleClient();

  unsigned long now = millis();
  handleSerialSpeed();

  float distance = getDistance();

  // ---------- Kiểm tra kẹt cảm biến ----------
  if (distance >= 800.0) {
    // Không có vật cản trong tầm đo -> không thể "kẹt", reset mốc thời gian
    lastDistanceChangeTime = now;
    lastDistance = -1.0;
  } else if (abs(distance - lastDistance) > DIST_TOLERANCE) {
    lastDistance = distance;
    lastDistanceChangeTime = now;
  }

  bool isStuck = (now - lastDistanceChangeTime >= STUCK_TIMEOUT_MS);
  const char* stateLabel;

  if (isStuck) {
    stopMotors();
    digitalWrite(BUZZER_PIN, HIGH);
    stateLabel = "STUCK";

    backUpAndTurn(DIR_LEFT);

    lastDistanceChangeTime = millis();
    lastDistance = -1.0;
    digitalWrite(BUZZER_PIN, LOW);
  }
  else if (distance <= 0 || distance >= WARN_DISTANCE) {
    moveForward(FULL_SPEED);
    digitalWrite(BUZZER_PIN, LOW);
    stateLabel = "DRIVE";
  }
  else if (distance >= STOP_DISTANCE) {
    moveForward(SLOW_SPEED);
    beepBuzzer(now);
    stateLabel = "SLOW";
  }
  else {
    stopMotors();
    digitalWrite(BUZZER_PIN, HIGH);
    stateLabel = "STOP";

    performRecoveryManeuver();
    lastDistanceChangeTime = millis();
    lastDistance = -1.0;
  }

  Serial.print(F("Dist: "));
  Serial.print(distance);
  Serial.print(F(" cm | State: "));
  Serial.print(stateLabel);
  Serial.print(F(" | Relay: "));
  Serial.println(relayState ? "ON" : "OFF");

  delay(50);
}

// ---------------- Điều khiển Relay & Wi-Fi Web Server ----------------

void setRelay(bool state) {
  relayState = state;
  if (RELAY_ACTIVE_LOW) {
    digitalWrite(RELAY_PIN, relayState ? LOW : HIGH);
  } else {
    digitalWrite(RELAY_PIN, relayState ? HIGH : LOW);
  }
}

void setupWiFi() {
  if (USE_AP_MODE) {
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASS);
    Serial.print(F("Wi-Fi AP Started. SSID: "));
    Serial.println(AP_SSID);
    Serial.print(F("Open browser at: http://"));
    Serial.println(WiFi.softAPIP()); // Mặc định là http://192.168.4.1
  } else {
    WiFi.mode(WIFI_STA);
    WiFi.begin(STA_SSID, STA_PASS);
    Serial.print(F("Connecting to Wi-Fi"));
    unsigned long startAttempt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < 10000) {
      delay(300);
      Serial.print(".");
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
      Serial.print(F("Connected! Open browser at: http://"));
      Serial.println(WiFi.localIP());
    } else {
      Serial.println(F("Wi-Fi connection failed! Running offline."));
    }
  }

  server.on("/", handleRoot);
  server.on("/relay/on", []() {
    setRelay(true);
    server.sendHeader("Location", "/");
    server.send(303);
  });
  server.on("/relay/off", []() {
    setRelay(false);
    server.sendHeader("Location", "/");
    server.send(303);
  });
  server.on("/relay/toggle", []() {
    setRelay(!relayState);
    server.sendHeader("Location", "/");
    server.send(303);
  });

  server.begin();
}

void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>ESP32 Robot Relay</title>";
  html += "<style>";
  html += "body{font-family:sans-serif;text-align:center;background:#121212;color:#fff;margin-top:50px;}";
  html += ".status{font-size:24px;margin:20px;font-weight:bold;color:" + String(relayState ? "#4CAF50" : "#F44336") + ";}";
  html += ".btn{display:inline-block;padding:18px 36px;font-size:20px;color:#fff;text-decoration:none;border-radius:10px;margin:10px;}";
  html += ".on{background:#2E7D32;} .off{background:#C62828;} .tog{background:#1565C0;}";
  html += "</style></head><body>";
  html += "<h1>ESP32 Robot Control</h1>";
  html += "<div class='status'>Relay: " + String(relayState ? "BẬT (ON)" : "TẮT (OFF)") + "</div>";
  html += "<a class='btn on' href='/relay/on'>BẬT RELAY</a>";
  html += "<a class='btn off' href='/relay/off'>TẮT RELAY</a><br>";
  html += "<a class='btn tog' href='/relay/toggle'>ĐẢO TRẠNG THÁI</a>";
  html += "</body></html>";

  server.send(200, "text/html", html);
}

// ---------------- Thao tác quét góc và chuyển hướng ----------------

// Thay cho delay(): vẫn phục vụ Web Server trong lúc chờ,
// nên trang điều khiển Relay không bị đơ khi robot đang quay xe.
void waitMs(unsigned long ms) {
  unsigned long start = millis();
  while (millis() - start < ms) {
    server.handleClient();
    delay(1);
  }
}

void performRecoveryManeuver() {
  myServo1.write(0);
  waitMs(SETTLE_MS);
  float distLeft = getDistance();

  if (distLeft < STOP_DISTANCE) {
    myServo1.write(180);
    waitMs(SETTLE_MS);
    float distRight = getDistance();

    if (distRight < STOP_DISTANCE) {
      myServo1.write(SERVO1_CENTER);
      waitMs(200);
      return;
    } else {
      backUpAndTurn(DIR_RIGHT);
    }
  } else {
    backUpAndTurn(DIR_LEFT);
  }

  myServo1.write(SERVO1_CENTER);
  waitMs(200);
  digitalWrite(BUZZER_PIN, LOW);
}

void backUpAndTurn(Direction dir) {
  moveBackward(TURN_SPEED);
  waitMs(BACKUP_MS);
  stopMotors();
  waitMs(100);

  if (dir == DIR_LEFT) {
    turnLeft(TURN_SPEED);
  } else {
    turnRight(TURN_SPEED);
  }
  waitMs(TURN_MS);
  stopMotors();
  waitMs(100);
}

// ---------------- Cảm biến siêu âm ----------------

float getDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 25000);
  if (duration == 0) return 999.0;

  return (duration * 0.0343) / 2.0;
}

// ---------------- Điều khiển động cơ (PWM) ----------------

void setMotors(int in1, int in2, int in3, int in4) {
  ledcWrite(IN1, in1);
  ledcWrite(IN2, in2);
  ledcWrite(IN3, in3);
  ledcWrite(IN4, in4);
}

void moveForward(int speed) {
  setMotors(speed, 0, speed, 0);
}

void moveBackward(int speed) {
  setMotors(0, speed, 0, speed);
}

void turnLeft(int speed) {
  setMotors(0, speed, speed, 0);
}

void turnRight(int speed) {
  setMotors(speed, 0, 0, speed);
}

void stopMotors() {
  setMotors(0, 0, 0, 0);
}

// ---------------- Buzzer ----------------

void beepBuzzer(unsigned long now) {
  if (now - lastBuzzerToggle >= BUZZER_BEEP_MS) {
    lastBuzzerToggle = now;
    buzzerBeepState = !buzzerBeepState;
    digitalWrite(BUZZER_PIN, buzzerBeepState ? HIGH : LOW);
  }
}

// ---------------- Chỉnh tốc độ qua Serial Monitor ----------------

void handleSerialSpeed() {
  if (!Serial.available()) return;

  char cmd = Serial.read();
  if (cmd == '\n' || cmd == '\r' || cmd == ' ') return; // bỏ ký tự xuống dòng thừa
  int value = Serial.parseInt();
  while (Serial.available()) Serial.read();

  value = constrain(value, 0, 255);

  if (cmd == 'f' || cmd == 'F') {
    FULL_SPEED = value;
    Serial.print(F("FULL_SPEED = "));
    Serial.println(FULL_SPEED);
  } else if (cmd == 's' || cmd == 'S') {
    SLOW_SPEED = value;
    Serial.print(F("SLOW_SPEED = "));
    Serial.println(SLOW_SPEED);
  } else if (cmd == 't' || cmd == 'T') {
    TURN_SPEED = value;
    Serial.print(F("TURN_SPEED = "));
    Serial.println(TURN_SPEED);
  }
}