"""CLI BB84, hậu xử lý giáo dục và ChaCha20-Poly1305."""

import argparse
import json
import sys

from bb84_lab.core.bb84 import Config
from bb84_lab.core.secure_channel import AuthenticationError
from bb84_lab.simulation.session import aead_demo, authenticated_session, integrated_session

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    bb84 = subparsers.add_parser("bb84", help="Mô phỏng, giám sát và hậu xử lý giáo dục")
    bb84.add_argument("--signals", type=int, default=4096)
    bb84.add_argument("--eve", type=float, default=0.0)
    bb84.add_argument("--noise", type=float, default=0.0)
    bb84.add_argument("--sample", type=float, default=0.25)
    bb84.add_argument("--threshold", type=float, default=0.05)
    bb84.add_argument("--min-samples", type=int, default=100)
    bb84.add_argument("--seed", type=int, default=2026)
    bb84.add_argument("--tamper-transcript", action="store_true")
    bb84.add_argument("--monitor-only", action="store_true", help="Chỉ giám sát, bỏ hậu xử lý")
    bb84.add_argument("--message", default="Xin chào từ BB84")
    aead = subparsers.add_parser("aead", help="Demo riêng bằng khóa ngẫu nhiên, không dùng khóa BB84")
    aead.add_argument("--message", default="Xin chào từ mô phỏng BB84")
    args = parser.parse_args()
    try:
        if args.command == "bb84":
            config = Config(args.signals, args.eve, args.noise, args.sample,
                            args.threshold, args.min_samples, args.seed)
            result = (authenticated_session(config, args.tamper_transcript) if args.monitor_only
                      else integrated_session(config, args.tamper_transcript, args.message))
        else:
            result = aead_demo(args.message)
    except AuthenticationError as error:
        parser.exit(2, f"Hủy phiên: {error}. Không phát hành khóa hoặc bản rõ.\n")
    except ValueError as error:
        parser.exit(2, f"Lỗi tham số: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
