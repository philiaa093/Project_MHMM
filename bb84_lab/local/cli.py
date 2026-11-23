"""Giao diện BB84 local: python -m bb84_lab.local --open."""

import argparse
from pathlib import Path
import sys
import webbrowser

from bb84_lab.local.server import make_server
from bb84_lab.shared.paths import OUTPUT_ROOT


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--study-dir", type=Path, default=OUTPUT_ROOT / "study")
    parser.add_argument("--open", action="store_true", help="Mở trình duyệt mặc định")
    args = parser.parse_args()
    try:
        server = make_server(args.port, args.study_dir)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Không khởi động được giao diện: {error}\n")
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"BB84 Lab: {url}\nMô phỏng cổ điển; nhấn Ctrl+C để dừng.", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
