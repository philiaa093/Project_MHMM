"""python -m bb84_lab.network: Internet/private-network Alice, Bob and Eve demo."""

import argparse
from pathlib import Path
import secrets
import sys
import threading
import webbrowser

from bb84_lab.network.config import DEFAULT_MAX_FILE_BYTES, network_config
from bb84_lab.network.proxy import ATTACK_MODES
from bb84_lab.network.service import NetworkNode, make_transport_server
from bb84_lab.network.ui import make_ui_server


def address(value):
    host, separator, port = value.rpartition(":")
    if not separator or not host or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise argparse.ArgumentTypeError("Địa chỉ cần dạng hostname:port hoặc IPv4:port")
    return host, int(port)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Demo mạng BB84 cổ điển: Alice → Eve (tùy chọn) → Bob")
    commands = parser.add_subparsers(dest="role", required=True)
    init = commands.add_parser("init", help="Tạo PSK riêng; chỉ sao chép cho Alice và Bob")
    init.add_argument("--psk-file", type=Path, default=Path("outputs/network/auth.key"))
    for role in ("alice", "bob", "eve"):
        command = commands.add_parser(role)
        command.add_argument("--ui-port", type=int, default=8770)
        command.add_argument("--open", action="store_true")
        if role != "eve":
            command.add_argument("--psk-file", type=Path, required=True)
            command.add_argument("--max-file-mib", type=int, default=DEFAULT_MAX_FILE_BYTES // 1024**2)
        if role != "alice":
            command.add_argument("--listen-host", default="127.0.0.1", help="Dùng IP VPN khi chạy khác máy")
            command.add_argument("--listen-port", type=int, default=9100 if role == "bob" else 9101)
        if role != "bob":
            command.add_argument("--target", type=address, required=True, help="Bob trực tiếp hoặc Eve: hostname:port")
        if role == "alice":
            command.add_argument("--signals", type=int, default=4096)
            command.add_argument("--seed", type=int, default=2026, help="Seed hoán vị Cascade công khai; bit sinh từ OS")
        if role == "bob":
            command.add_argument("--inbox", type=Path, default=Path("outputs/received"))
            command.add_argument("--noise", type=float, default=0)
        if role == "eve":
            command.add_argument("--mode", choices=sorted(ATTACK_MODES), default="pass")
            command.add_argument("--fraction", type=float, default=1.0)
            command.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    if args.role == "init":
        args.psk_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.psk_file.open("xb") as handle:
                handle.write(secrets.token_bytes(32))
        except FileExistsError:
            parser.error("Tệp PSK đã tồn tại; không ghi đè")
        print(f"Đã tạo PSK tại {args.psk_file}. Chỉ chuyển riêng tệp này cho Alice và Bob.")
        return
    if not 1 <= args.ui_port <= 65535:
        parser.error("Cổng giao diện phải từ 1 đến 65535")
    if args.role != "alice" and not 1 <= args.listen_port <= 65535:
        parser.error("Cổng truyền phải từ 1 đến 65535")
    if args.role != "eve":
        try:
            psk = args.psk_file.read_bytes()
        except OSError:
            parser.error("Không đọc được PSK. Chạy lệnh init rồi chuyển tệp riêng cho hai đầu")
        if len(psk) != 32 or not 1 <= args.max_file_mib <= 4096:
            parser.error("PSK phải đúng 32 byte; giới hạn tệp từ 1 đến 4096 MiB")
    else:
        psk = None
        if not 0 <= args.fraction <= 1 or args.seed < 0 or args.seed.bit_length() > 128:
            parser.error("fraction phải trong [0,1], seed từ 0 đến 2^128-1")
    if args.role == "bob" and not 0 <= args.noise <= 1:
        parser.error("noise phải trong [0,1]")
    config = None
    if args.role == "alice":
        try:
            config = network_config({"signals": args.signals, "seed": args.seed})
        except ValueError as error:
            parser.error(str(error))
    node = NetworkNode(args.role, psk, getattr(args, "target", None),
                       getattr(args, "inbox", "outputs/received"),
                       getattr(args, "max_file_mib", 512) * 1024**2,
                       getattr(args, "mode", "pass"), getattr(args, "fraction", 1),
                       getattr(args, "seed", 2026), getattr(args, "noise", 0))
    transport = None
    ui = None
    try:
        if args.role != "alice":
            transport = make_transport_server(node, args.listen_host, args.listen_port)
            threading.Thread(target=transport.serve_forever, daemon=True).start()
            print(f"{args.role.title()} TCP: {args.listen_host}:{args.listen_port}")
        ui = make_ui_server(node, args.ui_port, config)
        url = f"http://127.0.0.1:{args.ui_port}"
        print(f"Giao diện {args.role.title()}: {url}")
        print("Mô phỏng cổ điển, chỉ dùng dữ liệu demo. Ctrl+C để dừng.")
        if args.open:
            webbrowser.open(url)
        ui.serve_forever()
    except KeyboardInterrupt:
        pass
    except OSError:
        parser.exit(2, "Không mở được địa chỉ/cổng. Kiểm tra IP VPN, cổng đang dùng và tường lửa.\n")
    finally:
        if ui:
            ui.server_close()
        if transport:
            transport.shutdown()
            transport.server_close()
