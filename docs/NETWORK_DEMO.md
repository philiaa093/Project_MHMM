# Demo hai laptop khác mạng và máy ảo Eve

## 1. Kiến trúc

Mã backend nằm trong `bb84_lab/network/`: `session.py` phụ trách BB84,
`transfer.py` phụ trách tệp, `transport.py` phụ trách TCP và `proxy.py` là Eve.
Giao diện nằm trong `web/network/`. Xem cây mã đầy đủ tại
[REORGANIZATION.md](REORGANIZATION.md).

```text
Laptop Alice ── TCP tới Eve:9101 ── Máy thứ ba / VM Eve ── TCP tới Bob:9100 ── Laptop Bob
      │                                     │                                    │
dashboard local                       dashboard local                      dashboard local
127.0.0.1:8770                         127.0.0.1:8770                        127.0.0.1:8770
             Các máy cùng mạng riêng Tailscale qua Internet
```

Alice chủ động kết nối tới Eve; Eve chủ động kết nối tới Bob. Eve là proxy
được chọn tường minh, không cần chiếm quyền router. Có thể bỏ Eve bằng cách
cho Alice trỏ thẳng tới Bob. Các tiến trình độc lập, không có bộ nhớ chung,
không chuyển khóa ứng dụng giữa hai đầu.

Đây vẫn là **mô phỏng cổ điển**: trạng thái lượng tử là bit/cơ sở có thể đọc
và sao chép qua mạng. Đối thủ phần mềm thực tế có thể sao chép chúng mà
không gây QBER. Chặn–đo–gửi lại chỉ thực hiện quy tắc đo của mô hình; QBER
thấp không chứng minh bí mật hoặc vắng Eve. Chỉ dùng nội dung thử nghiệm.
Tailscale bảo vệ đường vận chuyển Internet riêng biệt với minh họa BB84.

## 2. Chuẩn bị thiết bị và mạng riêng

Sao chép mã nguồn lên hai laptop và máy/VM Eve. Cài Python cùng dependency
cơ bản, chạy PowerShell ở gốc dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tests.self_check
```

VM Linux dùng `.venv/bin/python` thay cho `.\.venv\Scripts\python.exe`.
Không cần Qiskit, Matplotlib, Node.js hay dependency Python mới.

Cài Tailscale trên **cả hai laptop và bên trong VM Eve**, đăng nhập để các
thiết bị tham gia cùng tailnet hoặc được chia sẻ/cho phép truy cập tương ứng.
VM có thể dùng mạng NAT của hypervisor; đăng nhập Tailscale bên trong VM để
có địa chỉ riêng. Kiểm tra bằng `tailscale status` và
`tailscale ping <IP-thiết-bị>`. Dùng IP Tailscale hoặc tên MagicDNS để kết
nối. Xem [cài đặt Tailscale](https://tailscale.com/docs/how-to/quickstart) và
[kết nối thiết bị](https://tailscale.com/docs/how-to/connect-to-devices).

Các IP bên dưới **là ví dụ**, cần thay bằng IP VPN thực:

| Vai trò | IP ví dụ | TCP cần nhận |
|---|---|---|
| Alice | `100.88.0.10` | Không cần cổng nhận dữ liệu |
| Bob | `100.88.0.20` | `9100` từ Eve, hoặc Alice khi đi thẳng |
| Eve | `100.88.0.30` | `9101` từ Alice |

Cho phép các luồng trên trong chính sách tailnet và tường lửa máy nhận.
Sau khi khởi động vai trò, kiểm tra trên Windows bằng
`Test-NetConnection 100.88.0.30 -Port 9101` từ Alice và
`Test-NetConnection 100.88.0.20 -Port 9100` từ Eve. Phép kiểm tra mở rồi đóng
TCP có thể tạo sự kiện kết nối lỗi trên dashboard; phiên gửi sau vẫn chạy.

Không cần port forwarding trên modem. Dashboard `8770` chỉ nghe loopback;
không mở cổng dashboard cho mạng ngoài.

## 3. PSK riêng cho Alice và Bob

Chạy **một lần trên một trong hai laptop**:

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.network init --psk-file outputs/network/auth.key
```

Lệnh tạo 32 byte ngẫu nhiên, không in khóa và từ chối ghi đè. Chuyển riêng
**đúng tệp đó** sang laptop còn lại qua kênh tin cậy, ví dụ USB hoặc SFTP đã
xác thực. Không chạy `init` riêng trên hai máy vì chúng sẽ tạo hai PSK khác
nhau. Không cấp tệp này cho Eve hoặc công khai nội dung. `outputs/` và
`*.key` được `.gitignore` bỏ qua. PSK dùng xác thực thảo luận công khai;
mỗi lần gửi tạo một khóa mô hình mới từ BB84/hậu xử lý.

## 4. Khởi động từng vai trò

**Laptop Bob**, chạy trước:

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.network bob --psk-file outputs/network/auth.key --listen-host 100.88.0.20 --listen-port 9100 --inbox outputs/received --open
```

**Máy/VM Eve**, trỏ tới Bob, không cần PSK:

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.network eve --listen-host 100.88.0.30 --listen-port 9101 --target 100.88.0.20:9100 --mode pass --open
```

**Laptop Alice**, trỏ tới Eve:

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.network alice --psk-file outputs/network/auth.key --target 100.88.0.30:9101 --open
```

Mỗi máy mở dashboard tại `http://127.0.0.1:8770`. Chọn **Gửi văn bản** hoặc
**Gửi tệp** trên Alice. Bob xem thông điệp/tệp đã xác thực trong hộp nhận.
QBER, Wilson, số bit giữ lại, đầu ra Toeplitz và nhật ký có ở hai đầu.
Nhấn `Ctrl+C` để dừng từng vai trò.

VM Linux không có giao diện đồ họa vẫn chạy Eve được: bỏ `--open`, dùng
`.venv/bin/python` và chọn `--mode` bằng CLI; khởi động lại Eve để đổi chế
độ nếu không dùng dashboard. Muốn đi thẳng thì Alice dùng
`--target 100.88.0.20:9100`.

Mặc định giới hạn 512 MiB/tệp. Có thể đặt cùng `--max-file-mib 1024` trên
Alice và Bob, giá trị từ 1 đến 4096 MiB. Văn bản tối đa 16.384 byte UTF-8.
Video là truyền tệp hoàn chỉnh rồi phát; chưa có webcam, gọi hoặc livestream.

## 5. Kịch bản trình diễn

Trên Eve, chọn chế độ rồi bấm **Áp dụng chế độ**, sau đó gửi một thông điệp
hoặc tệp **mới** trên Alice. Chế độ được chốt cho cả phiên; đổi khi bận bị
từ chối. Các kết quả bên dưới là hành vi mong đợi của mô hình; can thiệp
yếu có thể không bị QBER phát hiện.

| Chế độ Eve | Điều quan sát |
|---|---|
| Chỉ chuyển tiếp | Không nhiễu thì QBER 0%; đủ ngân sách thì Bob nhận đúng tệp |
| Chặn–đo–gửi lại, tỷ lệ 1 | QBER kỳ vọng 25% khi không nhiễu; thường hủy trước mã hóa |
| Chặn–đo–gửi lại, tỷ lệ 0,1 | Có thể không phát hiện; theo dõi Wilson và xác nhận khóa |
| Sửa một bit bản mã | AEAD từ chối, không phát hành tệp hoàn tất |
| Phát lại một gói | Bộ đếm phiên/thứ tự từ chối gói trùng |
| Ngắt truyền | Hủy tệp đang nhận khi kết nối đóng |
| Sửa thảo luận công khai | HMAC không khớp, hủy phiên |

Thử văn bản tiếng Việt, ảnh PNG/JPEG và video MP4/WebM. Mọi tệp đều truyền
như byte nhị phân; trình duyệt xem trước các định dạng media được cho phép
và codec nó hỗ trợ. Tệp khác vẫn tải về được. Có HTTP Range để tua video đã nhận.

## 6. Giao thức và lưu trữ

1. Bob phát challenge mới. Alice tạo ID phiên gắn challenge; các thông điệp
   công khai sau đó có HMAC-SHA256 và bộ đếm từng vai trò.
2. Alice sinh bit/cơ sở riêng bằng ngẫu nhiên OS. Eve có thể biến đổi trạng
   thái mô phỏng trước khi Bob đo bằng cơ sở ngẫu nhiên riêng.
3. Hai bên trao đổi cơ sở đã xác thực. Seed lấy mẫu được tạo **sau khi Bob
   đã đo**, hoán vị độc lập giá trị bit. Loại toàn bộ mẫu khỏi vật liệu khóa.
4. Bob tính QBER/Wilson, Alice đối chiếu từ mẫu Bob. Thiếu mẫu, bất thường
   hoặc khoảng cắt ngưỡng đều dừng trước mã hóa.
5. Bob dùng cùng lõi Cascade/lookback với demo cũ, hỏi parity Alice qua TCP.
   Mỗi truy vấn tính 2 bit rò rỉ; digest và phản hồi xác nhận tính 257 bit.
   Dùng cùng `key_budget`, biên mô hình 64 bit và Toeplitz. Dưới 256 bit
   đầu ra thì hủy; không chuyển khóa hoặc sao chép chuỗi Bob từ Alice.
6. Mỗi đầu lấy 256 bit ứng dụng và dùng HKDF ràng buộc phiên. Alice gửi gói
   kiểm tra khóa, Bob giải mã và xác nhận sẵn sàng trước dữ liệu người dùng.
7. Metadata tên/kích thước/hash, khối 64 KiB và dấu kết thúc đều dùng
   ChaCha20-Poly1305. AAD ràng buộc phiên/vai trò/thứ tự, nonce 96 bit tăng
   đơn điệu, mỗi lần gửi có phiên/khóa mới. Dùng API của
   [cryptography](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.ChaCha20Poly1305).
8. Bob xác thực từng khối, tổng byte, SHA-256 và dấu kết thúc rồi đổi `.part`
   thành tệp hoàn tất, gửi biên nhận HMAC. Lỗi trước bước này xóa tệp tạm.
   Alice chỉ báo thành công khi biên nhận khớp.

Bob lưu tại `outputs/received/<id>_<tên-đã-lọc>`, không ghi đè theo tên người
gửi. Đường dẫn/ký tự điều khiển trong tên bị loại. Upload Alice ghi theo khối
vào `outputs/network-staging/` rồi xóa khi worker kết thúc. Mỗi vai trò xử lý
một phiên tại một thời điểm; không gom toàn bộ tệp vào RAM. Dashboard giữ
tối đa 80 sự kiện và 100 mục nhận; tệp vẫn trên đĩa nhưng danh sách dashboard
không khôi phục sau khởi động lại. Khóa ứng dụng chỉ giữ ở RAM.

Dashboard Bob hiển thị bản rõ sau khi nhận thành công. Nhật ký không chứa
bản rõ, bản mã, PSK hoặc chuỗi bit. Nếu mất kết nối **sau khi Bob lưu tệp
nhưng trước biên nhận**, Alice báo lỗi dù Bob có thể đã nhận đủ: kiểm tra
hộp nhận trước khi gửi lại. Mỗi lần gửi là phiên mới, chưa tiếp tục truyền dở.
Tắt cưỡng bức/mất điện có thể để lại upload tạm hoặc `.part`; chúng không
phải tệp hoàn tất. Chỉ dọn thủ công khi không còn tiến trình đang dùng.

## 7. Thử ba vai trò trên một máy

Sau `init`, mở ba terminal riêng tại gốc dự án:

```powershell
# Terminal Bob
.\.venv\Scripts\python.exe -m bb84_lab.network bob --psk-file outputs/network/auth.key --ui-port 8770

# Terminal Eve
.\.venv\Scripts\python.exe -m bb84_lab.network eve --target 127.0.0.1:9100 --ui-port 8771

# Terminal Alice
.\.venv\Scripts\python.exe -m bb84_lab.network alice --psk-file outputs/network/auth.key --target 127.0.0.1:9101 --ui-port 8772
```

Mở `http://127.0.0.1:8770` cho Bob, `http://127.0.0.1:8771` cho Eve và
`http://127.0.0.1:8772` cho Alice. Không cần VPN cho bài thử loopback này.

## 8. Kiểm chứng và giới hạn

`python -m tests.self_check` kiểm tra socket thật: nhị phân nhiều khối, UTF-8,
tệp rỗng, đi thẳng/qua proxy, PSK sai, thiếu mẫu/ngân sách, chặn toàn phần,
sửa gói, phát lại, ngắt truyền, HMAC sai, upload HTTP, download/Range và không
còn tệp tạm sau lỗi.

Kiểm tra Chrome đã chạy ba tiến trình CLI riêng: văn bản UTF-8 có chuỗi giống
HTML được hiển thị đúng dạng văn bản, PNG xem được, MP4 phát được, tải video
về khớp byte gốc. Năm chế độ can thiệp và các cỡ màn hình 320/390/768/1440 px
đã được kiểm tra. Đây là kiểm chứng chức năng trên loopback.

Seed công khai được ghi để đối chiếu hoán vị/Cascade, seed Eve ghi tại proxy.
Bit/cơ sở mạng dùng OS randomness và không ghi lại; phiên mạng không tái lập
từng bit như bộ Monte Carlo. Dùng runner nghiên cứu cũ khi cần số liệu tái lập.

Các phép thử tự động chạy loopback. **Hai mạng Internet thật và VM của bạn**
cần kiểm chứng tại các thiết bị đó sau khi cài VPN/cấp quyền. Phạm vi là truyền
tệp một chiều Alice→Bob phục vụ demo, chưa phải hệ nhắn tin sản xuất hoặc
QKD vật lý.
