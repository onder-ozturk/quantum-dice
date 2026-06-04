#!/usr/bin/env python3
"""
Repeated REAL-HARDWARE characterisation of the hadamard-6q dice circuit, to
report run-to-run variance (TQE reviewer request).

Per backend we calibrate M3 readout-error mitigation once, then perform N_RUNS
independent runs of the production circuit (4000 shots each). For every run we
record the rejection-conditioned 1..6 TVD from uniform, before and after M3
mitigation, plus the chi^2 and acceptance. We then report mean +/- std over the
runs and dump everything for a box plot.

Credentials come from the environment / .env (NEVER hard-coded):
    IBM_QUANTUM_TOKEN   (required)
    IBM_CHANNEL         (default: ibm_cloud)

Writes figures/ibm_repeated_results.json (incrementally, so a queue stall never
loses completed runs).
"""
import os
import sys
import json
import collections
from datetime import datetime, timezone

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
QSVC = os.path.abspath(os.path.join(HERE, "..", "..", "quantum-service"))
sys.path.insert(0, QSVC)

from app.dice import build_dice_circuit, _decode_shot

SHOTS = int(os.environ.get("IBM_SHOTS", "4000"))
CAL_SHOTS = int(os.environ.get("IBM_CAL_SHOTS", "4000"))
N_RUNS = int(os.environ.get("IBM_N_RUNS", "5"))
N_BACKENDS = int(os.environ.get("IBM_N_BACKENDS", "2"))
TIMEOUT_S = int(os.environ.get("IBM_RESULT_TIMEOUT_S", "1800"))


def load_env(path):
    if not os.path.exists(path):
        return
    raw = open(path).read()
    s = raw.strip()
    if s.startswith("{"):
        try:
            blob = json.loads(s)
            key = blob.get("apikey") or blob.get("token") or blob.get("IBM_QUANTUM_TOKEN")
            if key and not os.environ.get("IBM_QUANTUM_TOKEN"):
                os.environ["IBM_QUANTUM_TOKEN"] = key
            return
        except Exception:
            pass
    for line in raw.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v and not os.environ.get(k):
                os.environ[k] = v


def cond_distribution(counts):
    """From {bitstring: weight} -> (cond_prob[1..6], acceptance, cond_counts_int)."""
    cond_mass = np.zeros(6)
    total_w = 0.0
    accept_w = 0.0
    for bs, w in counts.items():
        d1, d2 = _decode_shot(bs, 2)
        total_w += w
        if 1 <= d1 <= 6 and 1 <= d2 <= 6:
            accept_w += w
            cond_mass[d1 - 1] += w
            cond_mass[d2 - 1] += w
    cond_prob = cond_mass / cond_mass.sum() if cond_mass.sum() > 0 else cond_mass
    acceptance = accept_w / total_w if total_w else 0.0
    return cond_prob, acceptance, cond_mass


def tvd6(prob):
    return float(0.5 * np.sum(np.abs(prob - 1.0 / 6.0)))


def main():
    load_env(os.path.join(HERE, "..", ".env"))
    load_env(os.path.join(QSVC, ".env"))
    token = os.environ.get("IBM_QUANTUM_TOKEN")
    if not token:
        sys.exit("ERROR: IBM_QUANTUM_TOKEN not set.")
    channel = os.environ.get("IBM_CHANNEL", "ibm_cloud")

    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from mthree import M3Mitigation
    from mthree.utils import final_measurement_mapping

    print(f"Connecting to IBM Quantum (channel={channel})...")
    service = None
    for _ in range(4):
        try:
            service = QiskitRuntimeService(channel=channel, token=token)
            break
        except Exception as e:
            last = e
    if service is None:
        sys.exit(f"ERROR: QiskitRuntimeService init failed ({last}).")

    backends = service.backends(simulator=False, operational=True, min_num_qubits=6)

    def pending(b):
        try:
            return b.status().pending_jobs
        except Exception:
            return 10 ** 9

    backends = sorted(backends, key=pending)
    chosen, seen = [], set()
    for b in backends:
        if b.name not in seen:
            chosen.append(b); seen.add(b.name)
        if len(chosen) >= N_BACKENDS:
            break
    print("Chosen backends:", [b.name for b in chosen])

    all_results = []
    for b in chosen:
        name = b.name
        print(f"\n=== {name} ({b.num_qubits} qubits) ===")
        qc = build_dice_circuit(2)
        try:
            pm = generate_preset_pass_manager(optimization_level=1, backend=b,
                                              translation_method="translator")
        except Exception:
            pm = generate_preset_pass_manager(optimization_level=1, backend=b)
        isa = pm.run(qc)
        mapping = final_measurement_mapping(isa)
        print(f"calibrating M3 once (cal shots={CAL_SHOTS}); mapping={mapping}")
        mit = M3Mitigation(b)
        mit.cals_from_system(mapping, shots=CAL_SHOTS)

        sampler = SamplerV2(mode=b)
        raw_tvds, mit_tvds, runs = [], [], []
        for r in range(N_RUNS):
            job = sampler.run([isa], shots=SHOTS)
            jid = job.job_id()
            print(f"  run {r+1}/{N_RUNS}: job {jid} ...", flush=True)
            job.wait_for_final_state(timeout=TIMEOUT_S)
            counts = job.result()[0].data.c.get_counts()

            raw_p, acc, raw_mass = cond_distribution(counts)
            raw_tvd = tvd6(raw_p)
            cond_int = raw_mass.round().astype(int)
            chi2, p = stats.chisquare(cond_int, np.full(6, cond_int.sum() / 6.0))

            quasi = mit.apply_correction(counts, mapping)
            mprob = quasi.nearest_probability_distribution()
            mit_p, macc, _ = cond_distribution(mprob)
            mit_tvd = tvd6(mit_p)

            raw_tvds.append(raw_tvd); mit_tvds.append(mit_tvd)
            runs.append({"run": r + 1, "job_id": jid,
                         "raw_tvd_1to6": round(raw_tvd, 5),
                         "mit_tvd_1to6": round(mit_tvd, 5),
                         "chi2": round(float(chi2), 4), "p_value": round(float(p), 6),
                         "acceptance": round(acc, 5),
                         "raw_dist_1to6": [round(float(x), 5) for x in raw_p],
                         "mit_dist_1to6": [round(float(x), 5) for x in mit_p]})
            print(f"     raw TVD={raw_tvd:.4f}  mit TVD={mit_tvd:.4f}  chi2={chi2:.1f} p={p:.3f}")

            # incremental save
            entry = {"backend": name, "num_qubits": int(b.num_qubits),
                     "cal_shots": CAL_SHOTS, "shots": SHOTS, "runs": runs,
                     "raw_tvd_mean": round(float(np.mean(raw_tvds)), 5),
                     "raw_tvd_std": round(float(np.std(raw_tvds, ddof=1)) if len(raw_tvds) > 1 else 0.0, 5),
                     "mit_tvd_mean": round(float(np.mean(mit_tvds)), 5),
                     "mit_tvd_std": round(float(np.std(mit_tvds, ddof=1)) if len(mit_tvds) > 1 else 0.0, 5)}
            snapshot = [x for x in all_results if x["backend"] != name] + [entry]
            out = {"status": "running", "timestamp": datetime.now(timezone.utc).isoformat(),
                   "circuit": "hadamard-6q", "shots": SHOTS, "n_runs": N_RUNS,
                   "mitigation": "M3 (mthree), one calibration per backend",
                   "backends": snapshot}
            with open(os.path.join(HERE, "ibm_repeated_results.json"), "w") as f:
                json.dump(out, f, indent=2, default=float)

        all_results = [x for x in all_results if x["backend"] != name] + [entry]
        print(f"  {name}: raw TVD = {entry['raw_tvd_mean']:.4f} +/- {entry['raw_tvd_std']:.4f}, "
              f"mit TVD = {entry['mit_tvd_mean']:.4f} +/- {entry['mit_tvd_std']:.4f}")

    out = {"status": "done", "timestamp": datetime.now(timezone.utc).isoformat(),
           "circuit": "hadamard-6q", "shots": SHOTS, "n_runs": N_RUNS,
           "mitigation": "M3 (mthree), one calibration per backend",
           "backends": all_results}
    with open(os.path.join(HERE, "ibm_repeated_results.json"), "w") as f:
        json.dump(out, f, indent=2, default=float)

    print("\n=== SUMMARY (mean +/- std over runs) ===")
    for e in all_results:
        print(f"{e['backend']}: raw {e['raw_tvd_mean']:.4f}+/-{e['raw_tvd_std']:.4f}  "
              f"mit {e['mit_tvd_mean']:.4f}+/-{e['mit_tvd_std']:.4f}  (N={len(e['runs'])})")


if __name__ == "__main__":
    main()
