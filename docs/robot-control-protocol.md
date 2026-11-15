# Giao thức điều khiển robot — Phase 5 / 6A

REST, WebSocket và Device HTTP API Phase 6A đã triển khai. Firmware thật do Phase 6B thực hiện;
không có Robot Simulator. Hợp đồng HTTP cho ESP-IDF: [esp32-device-api.md](esp32-device-api.md).
Không có Emergency Stop endpoint hoặc nút Stop/Emergency Stop trên UI.

## 1. Nguồn trạng thái và quyền

PostgreSQL lưu lease, sequence, generation, requested mode, lịch sử lệnh và báo cáo thiết bị.
Không dùng biến global hoặc WebSocket connection làm nguồn lệnh duy nhất.

Mọi USER/ADMIN active được đọc robot active theo chính sách Phase 4. Quyền ghi yêu cầu JWT
còn hạn, auth session chưa thu hồi, robot active/Online và lease thuộc đúng user **và đúng
auth session**. ADMIN không được chiếm lease của người khác. UUID/role trong body không
thay thế kiểm tra backend. Lease token opaque chỉ lưu SHA-256 trong DB, plaintext trả một lần.

Online dựa trên heartbeat UTC, mặc định `ROBOT_OFFLINE_AFTER_SECONDS=15`. Timestamp tương
lai không hợp lệ. Busy = Online và lease còn hiệu lực. Robot mới luôn Offline.

## 2. REST API

Prefix `/api/v1/robots/{robot_id}/control`; header `Authorization: Bearer <access_token>`.
Response đặt `Cache-Control: no-store`. Không đặt token/credential/lease secret vào URL.

| Method/path | Body | Response |
| --- | --- | --- |
| POST `/acquire` | Không cần body | 201 LeaseGrant |
| POST `/renew` | LeaseInput | 200 LeaseView |
| POST `/release` | LeaseInput | 204 |
| GET `/session` | — | 200 LeaseView |
| GET `/state` | — | 200 ControlState |
| POST `/mode` | ActionInput + `mode` | 202 Command |
| POST `/move` | ActionInput + `direction` | 202 Command |
| POST `/stop` | ActionInput | 202 Command |

LeaseGrant: `id`, `owned`, `expires_at`, `lease_token`, `renew_after_ms`.
LeaseInput: `control_session_id` UUID và `lease_token` (32–128 ký tự).
ActionInput bổ sung `request_id` UUID, `client_sequence` số nguyên dương tăng theo lease.
Schema từ chối trường ngoài danh sách. Không gửi role, user ID hoặc server sequence.

Ví dụ body move (các giá trị đặt trong ngoặc nhọn là placeholder):

```json
{
  "control_session_id": "<UUID lease>",
  "lease_token": "<secret trong memory>",
  "request_id": "<UUID mới cho thao tác>",
  "client_sequence": 1,
  "direction": "FORWARD"
}
```

Direction của move chỉ nhận `FORWARD`, `BACKWARD`, `TURN_LEFT`, `TURN_RIGHT`.
Mode chỉ nhận `MANUAL`, `AUTO`. STOP được gửi qua `/stop`, không qua `/move`.

Command gồm `command_id`, `robot_id`, `control_session_id`, `sequence`, `generation`,
`kind`, `mode`, `direction`, `issued_at`, `expires_at`, `status`.
Kind: `MOVE`, `STOP`, `MODE`, `KEEPALIVE`. Status: `ACCEPTED`, `RECEIVED`, `APPLIED`,
`FAILED`, `REJECTED`, `SUPERSEDED`, `EXPIRED`. `EXECUTED` giữ tương thích adapter/test Phase 5;
Device HTTP API không nhận ACK EXECUTED.

**202/ACCEPTED chỉ là backend đã lưu yêu cầu.** RECEIVED là thiết bị nhận; APPLIED là firmware
báo đã chấp nhận áp dụng, không phải bằng chứng xe di chuyển. Backend không suy ra actual
movement/mode từ lệnh hoặc ACK thông thường. Safe handoff có báo cáo STOPPED/mode tường minh
là ngoại lệ xác nhận trạng thái handoff; telemetry còn lại do endpoint telemetry cung cấp.
SUPERSEDED/EXPIRED nghĩa lệnh không còn quyền thực thi, không phải xác nhận động cơ đã dừng.

Lỗi: 401 thiếu/hết hạn JWT hoặc phiên bị thu hồi; 403 sai lease/owner/secret;
404 robot không tồn tại hoặc không được xem; 409 Offline/Busy, thứ tự cũ, key xung đột hoặc
chưa xác nhận mode an toàn; 422 dữ liệu sai. Acquire robot inactive bị từ chối 409;
GET state/session trên robot inactive trả 404. Release lại lease đã đóng trả 403.

## 3. Lease và concurrency

Lease mặc định 10 giây. UI renew theo `renew_after_ms = min(2000, MODE_COMMAND_TTL_MS / 2)`
(mặc định 1500 ms), không renew chỉ vì trang Dashboard đang mở. Secret chỉ ở memory của
trang điều khiển, không lưu browser storage hoặc Query cache. Reload/rời trang không tự
chiếm lại lease. Khi mất lease cần chủ động Nhận điều khiển lại.

Acquire khóa hàng Robot, đóng lease cũ hết hạn trước INSERT; partial unique index hiện có
chỉ cho một lease chưa đóng/robot. Ghi lệnh khóa user, auth session, robot, lease và runtime
theo thứ tự nhất quán. Sequence tăng trong transaction; Move/Stop/Release/Mode được tuần tự
hóa trên PostgreSQL. Hai user tranh lease chỉ một người thành công.

Lease đóng khi release, timeout, Offline, robot/user bị disable, rotate credential, auth
session bị revoke (logout/password reset/refresh reuse), hoặc WebSocket của cùng phiên bị
ngắt. Trigger PostgreSQL đóng lease khi revoke auth và vô hiệu hóa lệnh khi `ended_at`
được đặt; không phụ thuộc vào đóng tab. Revoke một auth family không đóng các family khác.

Sweeper mỗi giây xử lý tối đa 100 robot cần cleanup bằng SKIP LOCKED; API đọc/ghi cũng kiểm
tra lại hạn ngay, không chờ sweeper. Device adapter kiểm tra hạn/fence trước trả lệnh.
Auth hết hạn cũng được kiểm tra trước cho lệnh; lease tối đa theo expiry hiện tại nếu không
có request nào nữa. Lease cũ không gắn auth session từ schema trước không được dùng để điều
khiển và bị đóng khi truy cập control service.

## 4. Ordering, TTL và replay

- `sequence` tăng theo robot suốt vòng đời, không reset khi đổi lease hoặc prune lịch sử.
- `generation` tăng khi acquire, Stop, đổi mode và đóng lease. Nó vô hiệu hóa các lệnh/báo
  cáo thuộc thế hệ cũ, kể cả lệnh đã gửi nhưng chưa thực thi.
- `client_sequence` là high-water mark theo lease; request mới có số nhỏ hơn/bằng bị 409.
  Frontend phân bổ trước khi xếp vào hàng đợi, serialize request và bỏ move đang chờ khi Stop.
- `request_id` có unique constraint theo robot. Cùng key/body trả cùng lệnh/trạng thái hiện
  tại; không làm sống lại lệnh đã bị thay thế/hết hạn. Cùng key, nội dung khác trả 409.
  Sau khi prune, high-water mark vẫn từ chối replay. Retry cùng thao tác phải giữ key/số.
- Lệnh mới thay thế lệnh hiện hành; không có hàng đợi chuyển động để phát lại sau reconnect.
- Manual MOVE và STOP TTL mặc định 700 ms, cấu hình 300–1500 ms. MODE/KEEPALIVE mặc định
  3000 ms, cấu hình 2000–5000 ms. Lệnh không-STOP không được sống lâu hơn lease.
- Hết TTL của chuyển mode chưa xác nhận hoặc Auto permit đóng lease. Manual đã xác nhận
  khi đứng yên vẫn giữ lease đến hạn/renew, dù MODE cũ đã hết TTL. Hết MOVE không duy trì
  chuyển động; thiết bị phải dừng, có thể nhận MOVE mới hợp lệ trong cùng lease.
- Lịch sử mặc định tối đa 1000 lệnh/robot; prune khi ghi, dọn lệnh kết thúc cũ hơn 7 ngày
  theo batch 1000. Không xóa sequence/generation khi dọn lịch sử.

STOP nội bộ thay thế chuyển động cũ, tăng generation. Sau STOP ở Manual đã xác nhận, vẫn
cho phép MOVE mới khi telemetry còn mới; sau STOP ở Auto/chuyển mode phải xác nhận Manual
an toàn. Device HTTP API Phase 6A không giao bất kỳ lệnh thuộc lease đã đóng, kể cả STOP.
Envelope null/không authorization tự nó bắt buộc STOP/hủy Auto. Adapter nội bộ Phase 5 vẫn
giữ ngoại lệ STOP để tương thích tests cũ, không phải đường giao tiếp firmware công khai.

## 5. Manual và frontend dead-man

D-Pad: Tiến trên, Lùi dưới, Quay trái bên trái, Quay phải bên phải. WASD hoặc Arrow Keys
tương ứng. Pointer Events hỗ trợ mouse/touch; giữ mới di chuyển, nhả/cancel gửi STOP.
Không có nút Stop riêng. Không gọi move khi actual mode chưa được xác nhận là Manual.

Mỗi request hoàn tất mới lên lịch refresh sau 250 ms, tối đa khoảng 4 request/giây.
Control POST có timeout 900 ms; có thể có khoảng dừng khi network chậm vì TTL ngắn. Không
kéo dài TTL để che lỗi mạng. Stop vô hiệu hóa move đang chờ ngay, rồi gửi sau request đang
bay; backend high-water mark/generation tiếp tục chặn thứ tự cũ khi request mạng đảo thứ tự.

Nhả nút dừng chuyển động nhưng giữ lease. Blur, tab ẩn, mất WebSocket, lệnh lỗi, timeout
lease, logout hoặc unmount ngừng refresh, cố gắng STOP/release. Response acquire đến muộn
sau khi trang bị đóng/mất focus cũng được release. Không coi request cleanup là bảo đảm
vật lý; TTL và watchdog firmware phải có hiệu lực khi request không tới backend/thiết bị.

## 6. Mode switching và Auto permit

Acquire luôn yêu cầu `MANUAL` và `mode_pending=true`, actual mode giữ null hoặc báo cáo
thực tế gần nhất. Manual → Auto: vô hiệu hóa Manual cũ, tăng generation, tạo MODE/AUTO với
direction STOP để yêu cầu handoff an toàn. Auto → Manual: tương tự, yêu cầu hủy Auto/dừng
chuyển động tự hành trước khi cấp Manual. UI không cho di chuyển khi pending.

Xác nhận an toàn qua Device HTTP API cần command_id/sequence/generation hiện hành, còn TTL,
`status=APPLIED`, `safe_mode_switch=true`, `actual_mode` khớp requested mode,
`actual_movement=STOPPED`. MODE APPLIED thiếu safe handoff bị từ chối 409. RECEIVED hoặc
telemetry thông thường không mở khóa Manual. Adapter DeviceReport/EXECUTED/STOP Phase 5
chỉ giữ để tương thích nội bộ, không dùng làm payload HTTP firmware.

Sau Auto được xác nhận, renew phát KEEPALIVE/AUTO có TTL ngắn; firmware chỉ chạy Auto khi
MODE/permit còn hợp lệ. Direction STOP trong MODE/KEEPALIVE không phải một lệnh chạy thẳng:
firmware xử lý theo kind/mode, dừng an toàn lúc handoff rồi mới cho thuật toán Auto chạy
trong permit. Permit hết hạn/null/fence đổi phải hủy Auto, dừng; không tự chạy lại thuật toán
cũ. Backend đóng lease khi permit hết hạn, cần acquire mới.

## 7. Trạng thái cảm biến, vật cản và Buzzer

ControlState trả `requested_mode`, `actual_mode`, `mode_pending`, `actual_movement`,
`obstacle`, `distance_cm`, `buzzer`, `reported_at`, `telemetry_fresh`, sequence/generation,
status, server_time và lease. Command/ID lease chỉ trả cho đúng phiên sở hữu; không trả secret.

Actual fields chỉ được cập nhật từ adapter xác thực thiết bị. Chưa có báo cáo: null;
UI hiển thị Chưa xác nhận/Chưa có dữ liệu/—. `telemetry_fresh` yêu cầu robot Online và báo
cáo còn mới theo heartbeat timeout. Khi stale, UI không hiển thị dữ liệu cũ như trạng thái mới.

| Obstacle | UI | Trách nhiệm firmware tương lai |
| --- | --- | --- |
| CLEAR | Phía trước thông thoáng | Chỉ báo theo dữ liệu cảm biến hợp lệ |
| BLOCKED | Có vật cản | Khóa chuyển động nguy hiểm, dừng và điều khiển Buzzer |
| SENSOR_ERROR | Lỗi cảm biến | Dừng fail-safe, báo lỗi cảm biến |
| null | Chưa có dữ liệu | Không suy diễn đường an toàn |

Khoảng cách nếu có phải hữu hạn, >=0; NaN/Infinity bị từ chối. Buzzer là boolean nullable,
chỉ hiển thị Bật/Tắt khi thiết bị cung cấp và telemetry còn mới. Không suy ra Buzzer hay
actual movement chỉ vì obstacle=BLOCKED hoặc người dùng giữ nút.

Yêu cầu phần cứng cho firmware sau: HC-SR04 phía trước đọc liên tục; Manual tiến khi khoảng
cách <15 cm phải dừng hai động cơ và bật còi. Khi an toàn trở lại tắt còi, chỉ thực thi lệnh
hợp lệ tiếp theo. Dữ liệu cảm biến lỗi phải dừng fail-safe. Lùi/quay cần chính sách riêng,
không giả định an toàn vì chỉ có cảm biến phía trước.

Auto chạy cục bộ: >=40 cm bình thường, 15–<40 cm giảm tốc, <15 cm dừng, servo quét trái/phải
để chọn hướng; không có hướng an toàn hoặc cảm biến lỗi thì dừng. Buzzer do firmware quản
lý. Backend không xử lý ngưỡng khoảng cách hoặc thay firmware quyết định lái xe.

## 8. WebSocket

`/api/v1/ws/robots/{robot_id}` cùng origin với web, dùng WSS trong production. Origin phải
khớp CORS_ORIGINS; mọi query string bị từ chối. Frame đầu trong 5 giây:

```json
{"type":"authenticate","access_token":"<JWT trong memory>"}
```

Không dùng cookie làm quyền điều khiển WS, không truyền token qua URL/subprotocol, không
ghi frame xác thực vào logs. Sau auth chỉ server gửi event; control commands qua REST.
Server kiểm tra JWT/session/user/robot lại mỗi snapshot. Mọi user active được subscribe
robot active theo Phase 4, kể cả xe Busy; chỉ chủ lease có thông tin lệnh riêng.

```json
{"type":"robot.state","data":{"robot_id":"<UUID>","status":"ONLINE","...":"ControlState đầy đủ"}}
```

Nếu không có thay đổi: `{"type":"ping","server_time":"<UTC ISO8601>"}`. Snapshot mới gửi
trạng thái hiện tại sau reconnect, không replay lịch sử; có seq/gen để phát hiện thay đổi.
Backend đọc DB mỗi giây (cấu hình 0.1–2 giây); không cần sticky worker/in-memory broker.
Đây là snapshot định kỳ qua WS, không phải PostgreSQL push notification tức thì.

Close codes: 4001 auth hết hạn/sai/thu hồi; 4003 robot không được truy cập; 1008 origin/query
hoặc message policy; 1011 lỗi DB. Trước accept có thể thấy HTTP handshake rejection.
Frontend refresh JWT qua client single-flight khi 4001; reconnect backoff 0.5→1→2→4→5 giây,
không tự reconnect khi 4003/1008. Không nhận state/ping trong 4 giây thì ngắt và release.
Khi kết nối mới chưa nhận snapshot, controls vẫn khóa. Unmount đóng socket/timers; REST
fallback đọc state mỗi 5 giây khi WS chưa kết nối, không làm quyền lái xe dựa trên polling.

## 9. Device HTTP API Phase 6A và watchdog

`DeviceService` phục vụ `/api/v1/devices` theo [hợp đồng Device API](esp32-device-api.md).
Tái dùng credential hash/rotation Phase 3 và ControlService Phase 5, khóa robot và tái kiểm
tra lease/TTL trước trả lệnh. Mọi request có credential headers, sau authenticate có device
session theo boot UUID. Auth/telemetry/poll không thay heartbeat. Reboot mới thu hồi lease,
fence thế hệ cũ, xóa actual state cached, giữ Offline cho tới heartbeat hợp lệ.

- GET commands/current trả desired mode, mode_pending, control_authorized,
  authorization_expires_at, lease_expires_at, server seq/gen, command|null, fail_safe=STOP.
- ACK RECEIVED/APPLIED/REJECTED/FAILED lưu timestamp/hash, không ACK chỉ vì poll. Duplicate
  đúng body trả receipt cũ, không cập nhật state/timestamp; không thể ghi đè lệnh mới.
  REJECTED/FAILED đóng lease. Safe handoff không suy diễn khoảng cách/Buzzer.
- Telemetry có sample_sequence theo boot, sequence high-water đã thấy và generation hiện
  tại, actual mode/movement, obstacle, distance, Buzzer. Lưu PostgreSQL, rate limit 5 Hz mặc
  định, retention 7 ngày/10000 mẫu mỗi robot. Duplicate không làm mới telemetry freshness.
- Command sequence/generation vẫn giữ khi reboot/prune. `DeviceControlService` với payload
  Phase 5 chỉ còn compatibility adapter nội bộ, không có route cho firmware.

Firmware Phase 6B phải giữ high-water sequence/generation/lease, bỏ lệnh
cũ, không thực thi lại duplicate; duplicate không được gia hạn expiry. Reboot/reconnect
phải handshake lại trước chạy, không tái dùng lệnh cache.

**command=null bắt buộc STOP và hủy Auto**, không mang nghĩa tiếp tục lệnh trước. STOP,
generation thay đổi, lease hết hạn, auth/heartbeat không hợp lệ, mất mạng, cảm biến lỗi hoặc
TTL hết phải chuyển động cơ về trạng thái an toàn tại ESP32. Timer watchdog cục bộ dùng
đồng hồ monotonic, hạn chặt nhất của TTL/lease/permit; heartbeat không tự gia hạn MOVE/Auto.
Đồng bộ giờ theo server_time khi tính expiry và trừ thời gian truyền; không cộng lại TTL
từ thời điểm nhận duplicate. Polling phải đủ nhanh so với TTL (dự kiến khoảng 100 ms),
không làm mới thời hạn nếu nhận lại cùng sequence. Các chi tiết mạng/clock và driver vật
lý cần kiểm thử trên ESP32 ở Phase 6B; Phase 6A chưa thể chứng minh thời gian dừng động cơ.
