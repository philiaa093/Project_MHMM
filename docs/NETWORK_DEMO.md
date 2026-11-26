# Demo truyền dữ liệu giữa hai máy

Chạy Alice và Bob trên hai máy cùng LAN hoặc VPN. Chọn **BB84** hoặc **E91**
trong **Giao thức tạo khóa** trên cả hai máy. Có thể chạy Eve ngay trên máy Alice
hoặc trên máy/VM riêng để minh họa tác động lên mô hình đường truyền.

## 1. Kiến trúc

Backend trong `bb84_lab/network/` gồm `setup.py` để khởi động vai trò từ
trình duyệt, `session.py` cho BB84 và hậu xử lý chung, `e91_session.py` cho
E91, `transfer.py` cho tệp, `transport.py` cho TCP và `proxy.py` cho Eve.
Giao diện nằm trong `web/network/`.
[Cây mã nguồn](REORGANIZATION.md)

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

Đây là **mô phỏng cổ điển**. Cả tín hiệu BB84 và mô tả cặp E91 đều là dữ
liệu TCP có thể đọc và sao chép. Một bên quan sát có thể chép chúng mà
không làm thay đổi QBER hay CHSH. PSK xác thực thảo luận công khai. Chỉ
dùng nội dung thử nghiệm. Tailscale bảo vệ đường vận chuyển Internet riêng
biệt với mô phỏng giao thức.

## 2. Chuẩn bị thiết bị và mạng riêng

Sao chép mã nguồn lên hai laptop và máy/VM Eve nếu dùng. Cài Python và các
gói phụ thuộc cơ bản. Chạy PowerShell ở gốc dự án.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tests.self_check
```

VM Linux dùng `.venv/bin/python` thay cho `.\.venv\Scripts\python.exe`.
Không cần Qiskit, Matplotlib, Node.js hay dependency Python mới.

Nếu hai laptop ở cùng LAN, dùng IPv4 Wi-Fi hoặc Ethernet của máy Bob. Khi
các máy ở khác mạng, cài Tailscale trên **cả hai laptop và bên trong VM Eve
nếu dùng**. Đăng nhập để các thiết bị tham gia cùng tailnet hoặc được chia
sẻ và cấp quyền truy cập tương ứng.
VM có thể dùng mạng NAT của hypervisor; đăng nhập Tailscale bên trong VM để
có địa chỉ riêng. Kiểm tra bằng `tailscale status` và
`tailscale ping <IP-thiết-bị>`. Dùng IP Tailscale hoặc tên MagicDNS để kết
nối. Giao diện thiết lập nhận địa chỉ IPv4.
[Cài đặt Tailscale](https://tailscale.com/docs/how-to/quickstart) ·
[Kết nối thiết bị](https://tailscale.com/docs/how-to/connect-to-devices)

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

### Thiết lập Alice và Bob trong trình duyệt

Trên cả hai máy, mở trang thiết lập tại `http://127.0.0.1:8770` bằng lệnh sau.

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.network setup --open
```

1. Bấm **Tạo PSK** trên một máy hoặc dùng PSK đã có. Đường dẫn mặc định là
   `outputs/network/auth.key`. Chuyển riêng tệp đó sang máy kia qua USB hoặc
   kênh tin cậy. Trên máy kia, bấm **Nhập tệp PSK** và chọn đúng tệp vừa chép.
2. Trên máy nhận, chọn **Bob** và chọn **BB84** hoặc **E91** ở **Giao thức tạo khóa**.
   Chạy `ipconfig` trong PowerShell để lấy IPv4 của máy này trên LAN hoặc
   VPN. Nhập IPv4 và cổng `9100`, rồi bấm
   **Khởi động Bob**. Cho phép TCP `9100` trong tường lửa của Bob nếu cần.
3. Trên máy gửi, chọn **Alice** và chọn cùng giao thức với Bob. Nhập IPv4 của
   Bob và cùng cổng `9100`, rồi bấm **Khởi động Alice**. Muốn chạy Eve cùng
   máy, chọn **Chạy kèm Eve trên máy Alice** trước khi khởi động. Hai đầu
   phải trùng giao thức thì mới thiết lập phiên được.
4. Trên Alice, bấm **Gửi văn bản** hoặc **Gửi tệp**. Kết quả hiện ở **Bob đã
   nhận**. Tệp hoàn tất nằm trong `outputs/received/` trên máy Bob.

### Xem log của phiên truyền

Xem **Terminal tạo khóa** trên dashboard Alice và Bob khi gửi thử. So mã phiên
ở hai đầu để đối chiếu các bước tương ứng. Terminal hiện log của phiên đang
chạy hoặc vừa kết thúc và ghi rõ bước dừng nếu có. Bấm **Xem log chi tiết**
rồi chọn **BB84** hoặc **E91** theo giao thức, **Cascade** hoặc **Toeplitz**.
Dùng **Trang trước**,
**Trang sau** hoặc nhập số trang để xem các dòng theo thứ tự thực thi.

- **BB84** hiện cặp cơ sở công khai của từng tín hiệu, kết quả sàng lọc, các
  bit đã công khai để lấy mẫu, QBER và khoảng Wilson.
- **E91** hiện số đếm của bốn tổ hợp đo Bell, phép ghép hệ số thành CHSH,
  QBER của mẫu từ hai nhóm đo cùng hướng và quyết định cho phiên đi tiếp.
- **Cascade** hiện từng truy vấn parity với 24 chỉ số đầu của khối và các
  giá trị parity đã trao đổi. Bob còn thấy các bước chia khối, lật bit và
  kiểm tra lại khối.
- **Toeplitz** hiện ngân sách, kích thước ma trận, toàn bộ seed công khai và
  24 hệ số đầu của mỗi hàng. Công thức và chỉ số seed cho phép dựng lại các
  hệ số còn lại. Terminal hiện bước xác nhận khóa ứng
  dụng sau khi khuếch đại riêng tư thành công.

Log nằm trong RAM, mỗi trang có tối đa 100 dòng. Mỗi giai đoạn lưu tối đa
8.192 dòng và đếm số dòng vượt giới hạn để hiển thị trên giao diện. Bấm
**Sao chép tóm tắt** để lưu các mốc chính trước khi chạy phiên tiếp theo.
PSK, khóa phiên, chuỗi bit giữ lại, giá trị đầu ra từng hàng Toeplitz và nội
dung gửi được giữ kín trong log.

Chọn **Tạo khóa từng bước** từ trang thiết lập hoặc dashboard để xem ví dụ
giảng dạy có đầy đủ bit đầu vào, phép nhân và bit đầu ra của Toeplitz.

Muốn đổi vai trò, địa chỉ, giao thức hoặc bật/tắt Eve đi kèm, nhấn `Ctrl+C`
rồi chạy lại lệnh `setup --open`. Để đổi giao thức, làm trên cả hai máy,
khởi động Bob trước và dùng lại PSK đang có. Chạy
`python -m bb84_lab.network setup --help` để xem tùy chọn tệp PSK và cổng
giao diện.

### Chạy Eve ngay trên máy Alice

1. Trên máy nhận, khởi động Bob như trên.
2. Trên trang thiết lập của máy gửi, chọn **Alice** và giao thức của Bob.
   Điền IPv4 và cổng TCP của Bob, chọn **Chạy kèm Eve trên máy Alice** rồi
   bấm **Khởi động Alice và Eve**.
   Cùng một trình khởi động mở Eve trên một cổng TCP loopback tự chọn và
   định tuyến Alice qua Eve tới Bob. Chỉ Alice và Bob dùng PSK.
3. Trên dashboard Alice, mở **Bảng điều khiển Eve**. Trang Eve dùng cùng
   cổng giao diện, mặc định là `http://127.0.0.1:8770/eve`. Mặc định Eve ở
   chế độ **Chỉ chuyển tiếp**. Để đổi chế độ, chọn tùy chọn trên trang Eve,
   bấm **Áp dụng chế độ**, rồi gửi một lượt mới trên Alice.

`Ctrl+C` trong cửa sổ trình khởi động trên máy gửi dừng cả Alice lẫn Eve.

## 3. Tạo PSK bằng dòng lệnh

Chạy **một lần trên một trong hai laptop**:

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.network init --psk-file outputs/network/auth.key
```

Lệnh tạo 32 byte ngẫu nhiên, không in khóa và từ chối ghi đè. Chuyển riêng
**đúng tệp đó** sang laptop còn lại qua kênh tin cậy, ví dụ USB hoặc SFTP đã
xác thực. Không chạy `init` riêng trên hai máy vì chúng sẽ tạo hai PSK khác
nhau. Không cấp tệp này cho Eve hoặc công khai nội dung. `outputs/` và
`*.key` được `.gitignore` bỏ qua. PSK dùng xác thực thảo luận công khai;
mỗi lần gửi tạo một khóa mô hình mới qua giao thức đã chọn và hậu xử lý.

## 4. Khởi động từng vai trò bằng dòng lệnh

Ví dụ dòng lệnh cho Alice và Bob dưới đây dùng BB84 mặc định. Dùng
**Setup** trên cả hai máy để chọn E91 từ giao diện.

**Laptop Bob**, chạy trước:

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.network bob --psk-file outputs/network/auth.key --listen-host 100.88.0.20 --listen-port 9100 --inbox outputs/received --open
```

**Máy/VM Eve**, trỏ tới Bob, không cần PSK:

```powershell
.\.venv\Scripts\python.exe -m bb84_lab.network eve --listen-host 100.88.0.30 --listen-port 9101 --target 100.88.0.20:9100 --mode pass --open
```

Eve chạy riêng hiển thị **Chưa xác định giao thức** cho đến khi quan sát
cấu hình phiên do Alice gửi. Dashboard sau đó hiện **BB84** hoặc **E91**,
đổi nhãn chế độ và các chỉ số tương ứng. Kết quả của lượt vừa chạy được giữ
đến khi có kết nối mới. Nhãn này dựa trên thông tin công khai mà Eve chuyển
tiếp. Alice và Bob xác thực cấu hình bằng PSK.

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
| Chặn–đo–gửi lại BB84, tỷ lệ 1 | QBER kỳ vọng 25% khi không nhiễu, thường hủy trước mã hóa |
| Chặn–đo–gửi lại BB84, tỷ lệ 0,1 | Có thể không phát hiện, theo dõi Wilson và xác nhận khóa |
| Làm mất tương quan E91, tỷ lệ 1 | Bob nhận kết quả độc lập, kỳ vọng \|S\| gần 0 và QBER mẫu gần 50%. Cổng CHSH thường dừng phiên trước mã hóa. |
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
2. Trong BB84, Alice sinh bit/cơ sở riêng bằng ngẫu nhiên OS. Eve có thể
   biến đổi trạng thái mô phỏng trước khi Bob đo bằng cơ sở ngẫu nhiên
   riêng. Trong E91, Alice tạo mô tả cổ điển cho 8.192 cặp mặc định và Bob
   chọn hướng đo độc lập. Hai đầu xác thực và đối chiếu dữ liệu của bốn
   tổ hợp Bell, dùng hai tổ hợp cùng hướng cho nguồn bit khóa. Bob đảo
   kết quả cùng hướng để chuyển đối tương quan lý tưởng thành các bit khớp.
3. Hai bên trao đổi cơ sở đã xác thực. Seed lấy mẫu được tạo **sau khi Bob
   đã đo**, hoán vị độc lập giá trị bit. Loại toàn bộ mẫu khỏi vật liệu khóa.
4. Bob tính QBER/Wilson, Alice đối chiếu từ mẫu Bob. Thiếu mẫu, bất thường
   hoặc khoảng cắt ngưỡng đều dừng trước mã hóa. E91 còn yêu cầu cận dưới
   của khoảng 95% cho `|S|` lớn hơn 2 trước khi cho phép đối soát.
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

`python -m tests.self_check` kiểm tra socket thật. Phần mạng gồm truyền tệp
BB84 và E91, phiên E91 dừng tại CHSH, hai đầu chọn khác giao thức, nhị phân
nhiều khối, UTF-8, tệp rỗng, đi thẳng hoặc qua proxy, PSK sai, thiếu mẫu
hoặc ngân sách, sửa gói, phát lại, ngắt truyền, HMAC sai, upload HTTP,
download/Range và dọn tệp tạm sau lỗi.

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
