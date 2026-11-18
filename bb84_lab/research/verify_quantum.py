"""Đối chiếu quy tắc Monte Carlo bằng mạch một qubit Qiskit và Aer."""

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys


def check_quantum(shots=8192, seed=1701):
    if not __debug__:
        raise ValueError("Không dùng -O khi kiểm chứng vì tùy chọn đó tắt assert")
    if type(shots) is not int or shots < 1024 or shots > 1_000_000:
        raise ValueError("shots phải là số nguyên từ 1024 đến 1000000")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed phải là số nguyên không âm")
    from qiskit import QuantumCircuit, transpile
    from qiskit.quantum_info import Statevector
    from qiskit_aer import AerSimulator

    cases = []
    circuits = []
    exact_errors = []
    for bit in (0, 1):
        for alice_basis in (0, 1):
            for bob_basis in (0, 1):
                circuit = QuantumCircuit(1, 1)
                if bit:
                    circuit.x(0)
                if alice_basis:
                    circuit.h(0)
                if bob_basis:
                    circuit.h(0)
                probability_one = float(Statevector.from_instruction(circuit.remove_final_measurements(inplace=False)).probabilities()[1])
                expected = float(bit) if alice_basis == bob_basis else .5
                assert abs(probability_one - expected) < 1e-12
                circuit.measure(0, 0)
                circuits.append(circuit)
                cases.append({"alice_bit": bit, "alice_basis": alice_basis, "bob_basis": bob_basis,
                              "expected_p_one": expected, "exact_p_one": probability_one})
    # Eve chooses a basis uniformly; condition on her measurement, then prepare
    # exactly the state she resends. Bob uses Alice's basis after sifting.
    for bit in (0, 1):
        for alice_basis in (0, 1):
            error_probability = 0.0
            for eve_basis in (0, 1):
                prepared = QuantumCircuit(1)
                if bit:
                    prepared.x(0)
                if alice_basis:
                    prepared.h(0)
                if eve_basis:
                    prepared.h(0)
                eve_probabilities = Statevector.from_instruction(prepared).probabilities()
                for eve_bit in (0, 1):
                    resent = QuantumCircuit(1)
                    if eve_bit:
                        resent.x(0)
                    if eve_basis:
                        resent.h(0)
                    if alice_basis:
                        resent.h(0)
                    bob_probabilities = Statevector.from_instruction(resent).probabilities()
                    error_probability += .5 * float(eve_probabilities[eve_bit]) * float(bob_probabilities[1 - bit])
            assert abs(error_probability - .25) < 1e-12
            exact_errors.append(error_probability)
    simulator = AerSimulator()
    counts = simulator.run(transpile(circuits, simulator, seed_transpiler=seed), shots=shots, seed_simulator=seed).result().get_counts()
    for case, count in zip(cases, counts):
        measured = count.get("1", 0) / shots
        expected = case["expected_p_one"]
        tolerance = 5 * (expected * (1 - expected) / shots) ** .5 + 1 / shots
        assert abs(measured - expected) <= tolerance, (case, measured)
        case["aer_p_one"] = measured
    return {"status": "passed", "qiskit": importlib.metadata.version("qiskit"),
            "qiskit_aer": importlib.metadata.version("qiskit-aer"), "shots_per_case": shots,
            "seed": seed, "prepare_measure_cases": cases, "eve_full_exact_qber": sum(exact_errors) / len(exact_errors),
            "scope": "Independent one-qubit circuit checks; classical simulation, no hardware claim"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shots", type=int, default=8192)
    parser.add_argument("--seed", type=int, default=1701)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.exit(2, "Tệp output đã tồn tại; không ghi đè.\n")
    try:
        result = check_quantum(args.shots, args.seed)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
    except (ImportError, OSError, ValueError) as error:
        parser.exit(2, f"Lỗi: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
