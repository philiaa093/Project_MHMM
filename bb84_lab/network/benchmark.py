"""Measure real two-process loopback file transfers with the existing protocol.

No dashboard, no monkeypatched RNG, no keys or authentication files are saved.
The optional psutil sampler reports the combined sender/receiver RSS and CPU.
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
from pathlib import Path
import platform
import secrets
import socket
import statistics
import sys
import threading
import time

from bb84_lab.core.bb84 import wilson_interval
from bb84_lab.network.config import network_config
from bb84_lab.network.transfer import receive_transfer, send_transfer
from bb84_lab.shared.paths import PROJECT_ROOT


def _receiver(pipe, psk, inbox, protocol, noise):
    result = {"state": "not_started", "cpu_seconds": 0.}
    cpu = time.process_time()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(30)
            pipe.send({"port": listener.getsockname()[1]})
            with listener.accept()[0] as connection:
                item = receive_transfer(connection, psk, inbox, noise=noise, protocol=protocol)
        result.update(state="complete" if item else "aborted", size=item["size"] if item else 0,
                      sha256=item["sha256"] if item else None)
    except Exception as error:
        result.update(state="failed", error_type=type(error).__name__)
    finally:
        result["cpu_seconds"] = time.process_time() - cpu
        try:
            pipe.send(result)
        finally:
            pipe.close()


def run_trial(protocol, path, inbox, signals=8192, noise=0., resources=True):
    """Start an independent receiver; exclude process startup from timings."""
    config = network_config({"signals": signals})
    if protocol not in ("bb84", "e91"):
        raise ValueError("Unknown protocol")
    if type(noise) not in (int, float) or not 0 <= noise <= 1:
        raise ValueError("Invalid noise")
    path, inbox = Path(path), Path(inbox)
    expected_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    parent_pipe, child_pipe = multiprocessing.get_context("spawn").Pipe()
    psk = secrets.token_bytes(32)
    process = multiprocessing.get_context("spawn").Process(
        target=_receiver, args=(child_pipe, psk, str(inbox), protocol, noise))
    process.start()
    child_pipe.close()
    stop = threading.Event()
    samples, sampler_errors, thread = [], [], None
    result = None
    try:
        if not parent_pipe.poll(30):
            raise TimeoutError("Receiver startup timed out")
        ready = parent_pipe.recv()
        if "port" not in ready:
            raise RuntimeError("Receiver could not start")
        resource_status = "disabled"
        if resources:
            try:
                import psutil
            except ImportError:
                resource_status = "psutil_unavailable"
            else:
                endpoints = [psutil.Process(), psutil.Process(process.pid)]

                def sample():
                    while not stop.is_set():
                        try:
                            samples.append(sum(endpoint.memory_info().rss for endpoint in endpoints))
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as error:
                            sampler_errors.append(type(error).__name__)
                            break
                        stop.wait(.01)

                thread = threading.Thread(target=sample, daemon=True)
                thread.start()
                resource_status = "sampled"
        events = {}

        def event(code, message, **data):
            if code in ("connecting", "key_trace_begin", "qber", "key", "complete", "aborted"):
                events[code] = time.perf_counter()

        start, cpu = time.perf_counter(), time.process_time()
        result = send_transfer(("127.0.0.1", ready["port"]), psk, path, config=config,
                               event=event, protocol=protocol)
        elapsed, sender_cpu = time.perf_counter() - start, time.process_time() - cpu
        if not parent_pipe.poll(30):
            raise TimeoutError("Receiver result timed out")
        received = parent_pipe.recv()
        verified = (result["state"] == received["state"] == "complete"
                    and result["sha256"] == received["sha256"] == expected_hash
                    and received["size"] == path.stat().st_size)
        if result["state"] == "complete" and not verified:
            raise AssertionError("Sender/receiver receipt mismatch")
        stats = result["statistics"]
        key_time = events.get("key")
        transfer_seconds = events["complete"] - key_time if verified else None
        post_seconds = key_time - events["qber"] if key_time else None
        return {
            "protocol": protocol, "signals": signals, "noise_probability": noise,
            "payload_bytes": path.stat().st_size, "state": result["state"], "verified": verified,
            "receiver_state": received["state"], "monitor_status": stats["status"],
            "sifted_bits": stats["sifted_bits"], "sample_bits": stats["sample_count"],
            "retained_bits": stats["retained_bits"], "parity_leak_bits": stats.get("parity_leak_bits", 0),
            "y_final": stats.get("output_bits", 0) if key_time else 0,
            "key_setup_seconds": key_time - start if key_time else None,
            "postprocessing_seconds": post_seconds, "file_transfer_seconds": transfer_seconds,
            "end_to_end_seconds": elapsed,
            "payload_mib_per_second": path.stat().st_size / (1024 ** 2) / transfer_seconds if transfer_seconds else None,
            "end_to_end_mib_per_second": path.stat().st_size / (1024 ** 2) / elapsed if verified else None,
            "sender_cpu_seconds": sender_cpu, "receiver_cpu_seconds": received["cpu_seconds"],
            "combined_cpu_one_core_percent": 100 * (sender_cpu + received["cpu_seconds"]) / elapsed,
            "combined_rss_baseline_bytes": samples[0] if samples else None,
            "combined_rss_sampled_peak_bytes": max(samples) if samples else None,
            "combined_rss_peak_increment_bytes": max(samples) - samples[0] if samples else None,
            "rss_samples": len(samples), "rss_interval_seconds": .01,
            "resource_status": resource_status, "resource_sampler_errors": ",".join(sorted(set(sampler_errors))),
            "payload_sha256": expected_hash,
        }
    finally:
        stop.set()
        if thread:
            thread.join(timeout=2)
        parent_pipe.close()
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)


def summarize(rows):
    groups = {}
    for row in rows:
        key = (row["budget_mode"], row["budget"], row["protocol"], row["payload_bytes"], row["noise_probability"])
        groups.setdefault(key, []).append(row)
    result = []
    fields = ("key_setup_seconds", "postprocessing_seconds", "file_transfer_seconds", "end_to_end_seconds",
              "payload_mib_per_second", "end_to_end_mib_per_second", "combined_cpu_one_core_percent",
              "combined_rss_sampled_peak_bytes", "combined_rss_peak_increment_bytes", "y_final")
    for key, group in sorted(groups.items()):
        complete = sum(row["verified"] for row in group)
        item = {**dict(zip(("budget_mode", "budget", "protocol", "payload_bytes", "noise_probability"), key)),
                "sessions": len(group), "complete_count": complete, "complete_rate": complete / len(group),
                "complete_ci95": wilson_interval(complete, len(group))}
        for name in fields:
            values = [row[name] for row in group if row[name] is not None]
            item[name + "_observations"] = len(values)
            item[name + "_median"] = statistics.median(values) if values else None
            item[name + "_mean"] = statistics.fmean(values) if values else None
            item[name + "_min"] = min(values) if values else None
            item[name + "_max"] = max(values) if values else None
        result.append(item)
    return result


def run_benchmark(output, *, repeats=20, budget=8192, sizes=(65536, 1048576), noise=0., resources=True, warmup=True):
    if type(repeats) is not int or repeats < 1:
        raise ValueError("repeats must be positive")
    if type(budget) is not int or budget < 2 or budget % 2 or budget > 65536:
        raise ValueError("budget must be even and in [2,65536]")
    if not sizes or any(type(size) is not int or not 1 <= size <= 16 * 1024 ** 2 for size in sizes):
        raise ValueError("payload sizes must be in [1,16 MiB]")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    def fingerprints():
        return {str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
                for domain in ("core", "network") for path in sorted((PROJECT_ROOT / "bb84_lab" / domain).glob("*.py"))}
    source_hashes = fingerprints()
    manifest = {
        "state": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(), "processor": platform.processor(),
        "repeats": repeats, "budget": budget, "sizes": sizes, "noise": noise,
        "source_sha256": source_hashes,
        "transport": "127.0.0.1 TCP; independent sender and spawned receiver process; no Eve proxy or dashboard",
        "randomness": "OS randomness for protocol/PSK/Toeplitz; exact measurement outcomes are not seed-reproducible",
        "ordering": "alternating protocol order per repeat, within size and budget; serial",
        "warmup": "one excluded run per protocol and budget mode at smallest size" if warmup else "none",
        "timing": "perf_counter; starts before source hash and TCP connect; excludes receiver process startup",
        "postprocessing": "QBER event to confirmed key event; includes TCP, Cascade, confirmation, Toeplitz and key handshake",
        "throughput": "verified payload MiB / (receipt time - confirmed key event); also report end-to-end rate",
        "cpu": "sender process_time + receiver process_time (receiver begins before socket bind); percent of one core, may exceed 100",
        "ram": "sampled sum of sender and receiver RSS every 10 ms; includes baseline and sampler overhead; may miss short peaks",
        "scope": "software loopback benchmark; synthetic public byte-pattern payload, not physical QKD performance",
    }

    def save(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    save("manifest.json", manifest)
    rows, warmups = [], []
    started = time.perf_counter()
    try:
        for size in sizes:
            path = output / f"public-benchmark-{size}.bin"
            block = bytes(range(256))
            path.write_bytes((block * ((size + 255) // 256))[:size])
            for mode in ("equal_signals", "equal_measurements"):
                for repeat in range(-1 if warmup and size == sizes[0] else 0, repeats):
                    for protocol in (("bb84", "e91") if repeat % 2 == 0 else ("e91", "bb84")):
                        signals = budget // 2 if protocol == "e91" and mode == "equal_measurements" else budget
                        trial = {"budget_mode": mode, "budget": budget, "repeat": repeat,
                                 **run_trial(protocol, path, output / "received", signals, noise, resources)}
                        (warmups if repeat < 0 else rows).append(trial)
                with (output / "sessions.csv").open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                print(f"{mode}/{size} bytes: {len(rows)} measured transfers", flush=True)
        save("summary.json", summarize(rows))
        save("warmups.json", warmups)
        if fingerprints() != source_hashes:
            raise RuntimeError("Source changed during benchmark")
        manifest.update(state="complete", measured_sessions=len(rows), verified_transfers=sum(row["verified"] for row in rows),
                        elapsed_seconds=time.perf_counter() - started,
                        artifacts_sha256={name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                          for name in ("sessions.csv", "summary.json", "warmups.json")})
        save("manifest.json", manifest)
    except Exception as error:
        manifest.update(state="failed", error_type=type(error).__name__, completed_sessions=len(rows))
        save("manifest.json", manifest)
        raise
    return manifest


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--budget", type=int, default=8192)
    parser.add_argument("--sizes", type=int, nargs="+", default=[65536, 1048576])
    parser.add_argument("--noise", type=float, default=0.)
    parser.add_argument("--no-resources", action="store_true")
    parser.add_argument("--no-warmup", action="store_true")
    args = parser.parse_args()
    result = run_benchmark(args.output, repeats=args.repeats, budget=args.budget, sizes=tuple(args.sizes),
                           noise=args.noise, resources=not args.no_resources, warmup=not args.no_warmup)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
