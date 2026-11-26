"""Run all assert-based suites: python -m tests.self_check (without -O)."""

import sys

from bb84_lab.core.secure_channel import check_secure_channel
from bb84_lab.research.study import check_research
from tests.check_core import check_bb84, check_e91, check_postprocessing
from tests.check_local_http import check_http
from tests.check_network import check_network
from tests.check_research import check_experiments, check_study
from tests.check_simulation import check_demo, check_education
from tests.check_structure import check_project_structure


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if not __debug__:
        raise SystemExit("Chạy python -m tests.self_check; không dùng -O vì sẽ tắt assert.")
    check_project_structure()
    check_bb84()
    check_e91()
    check_secure_channel()
    check_demo()
    check_education()
    check_experiments()
    check_postprocessing()
    check_research()
    check_study()
    check_http()
    check_network()
    print("PASS: BB84/QBER, E91/CHSH, Cascade/Toeplitz, AEAD/nonce/replay, HTTP, truyền tệp Alice–Eve–Bob và nghiên cứu tái lập.")
    print("Khóa từ seed công khai chỉ dùng minh họa; không bảo vệ dữ liệu thật.")


if __name__ == "__main__":
    main()
