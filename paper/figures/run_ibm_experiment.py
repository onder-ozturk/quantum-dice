#!/usr/bin/env python3
"""
Preliminary REAL-HARDWARE run of the production hadamard-6q dice circuit.

Runs the exact same circuit (app.dice.build_dice_circuit(2)) on the least-busy
real IBM Quantum backend and measures how hardware noise perturbs the raw 0..7
distribution and the rejection-conditioned 1..6 dice distribution.

Credentials come from the environment / quantum-service/.env (NEVER hard-coded):
    IBM_QUANTUM_TOKEN   (required)
    IBM_CHANNEL         (default: ibm_quantum_platform; or ibm_cloud)
    IBM_INSTANCE        (optional CRN / hub-group-project)

Saves figures/ibm_experiment_results.json and prints LaTeX-ready numbers.
If the job is still queued after the timeout, the job id is saved and the
script exits gracefully so it can be re-checked later.
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

from app.dice import build_dice_circuit, _decode_shot  # exact production circuit + decoder

SHOTS = int(os.environ.get("IBM_SHOTS", "4000"))
TIMEOUT_S = int(os.environ.get("IBM_RESULT_TIMEOUT_S", "900"))


def load_env(path):
    """Minimal .env loader (does not overwrite already-set env vars)."""
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v and not os.environ.get(k):
                os.environ[k] = v


def bitstrings_from_pub(pub_result):
    """Robustly pull per-shot bitstrings from a SamplerV2 PubResult."""
    data = pub_result.data
    ba = getattr(data, "c", None)
    if ba is None:
        # fall back to the first (only) classical register
        for k in (data.keys() if hasattr(data, "keys") else []):
            ba = data[k]
            break
    if ba is None:
        ba = pub_result.join_data()
    return list(ba.get_bitstrings())


def main():
    load_env(os.path.join(QSVC, ".env"))
    token = os.environ.get("IBM_QUANTUM_TOKEN")
    if not token:
        sys.exit("ERROR: IBM_QUANTUM_TOKEN not set (put it in quantum-service/.env or export it).")
    channel = os.environ.get("IBM_CHANNEL", "ibm_quantum_platform")
    instance = os.environ.get("IBM_INSTANCE") or None

    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

    print(f"Connecting to IBM Quantum (channel={channel})...")
    kwargs = {"channel": channel, "token": token}
    if instance:
        kwargs["instance"] = instance
    try:
        service = QiskitRuntimeService(**kwargs)
    except Exception as e:
        sys.exit(f"ERROR: could not init QiskitRuntimeService ({e}). "
                 f"Check token and channel (try IBM_CHANNEL=ibm_cloud).")

    backend = service.least_busy(operational=True, simulator=False)
    status = backend.status()
    print(f"Backend: {backend.name} ({backend.num_qubits} qubits), pending jobs: "
          f"{getattr(status, 'pending_jobs', '?')}")

    qc = build_dice_circuit(2)
    # Force the standard Qiskit translator: newer Heron backends advertise an
    # 'ibm_dynamic_circuits' translation plugin our simple H+measure circuit doesn't need.
    try:
        pm = generate_preset_pass_manager(optimization_level=1, backend=backend,
                                          translation_method="translator")
    except Exception:
        pm = generate_preset_pass_manager(optimization_level=1, backend=backend)
    isa = pm.run(qc)

    sampler = SamplerV2(mode=backend)
    job = sampler.run([isa], shots=SHOTS)
    job_id = job.job_id()
    print(f"Submitted job {job_id} with {SHOTS} shots. Waiting (timeout {TIMEOUT_S}s)...")

    try:
        job.wait_for_final_state(timeout=TIMEOUT_S)
    except Exception as e:
        out = {"status": "pending", "job_id": job_id, "backend": backend.name,
               "shots": SHOTS, "note": f"not finished within {TIMEOUT_S}s ({e}); re-run with "
               f"IBM_JOB_ID={job_id} to fetch later."}
        with open(os.path.join(HERE, "ibm_experiment_results.json"), "w") as f:
            json.dump(out, f, indent=2)
        sys.exit(f"Job still {getattr(job,'status',lambda:'queued')()}; saved job_id and exited.")

    result = job.result()
    memory = bitstrings_from_pub(result[0])
    print(f"Got {len(memory)} shots from {backend.name}.")

    # raw per-die marginal over 0..7 (both dice pooled) and conditioned 1..6
    raw = collections.Counter()
    cond = collections.Counter()
    valid_pairs = 0
    for bs in memory:
        d1, d2 = _decode_shot(bs, 2)
        raw[d1] += 1; raw[d2] += 1
        if 1 <= d1 <= 6 and 1 <= d2 <= 6:
            valid_pairs += 1
            cond[d1] += 1; cond[d2] += 1

    n_raw = sum(raw.values())               # = 2 * shots
    raw_counts = [raw.get(k, 0) for k in range(8)]
    raw_tvd = 0.5 * sum(abs(c / n_raw - 1 / 8) for c in raw_counts)

    n_cond = sum(cond.values())
    cond_counts = [cond.get(k, 0) for k in range(1, 7)]
    exp_cond = np.full(6, n_cond / 6.0)
    chi2, p = stats.chisquare(np.array(cond_counts), exp_cond)
    cond_tvd = 0.5 * sum(abs(c / n_cond - 1 / 6) for c in cond_counts)
    accept = valid_pairs / len(memory)

    res = {
        "status": "done",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "backend": backend.name,
        "num_qubits": backend.num_qubits,
        "job_id": job_id,
        "shots": SHOTS,
        "circuit": "hadamard-6q",
        "raw_0to7": {"counts": {str(k): raw_counts[k] for k in range(8)},
                     "tvd_from_uniform_1_8": round(raw_tvd, 5)},
        "conditioned_1to6": {"counts": {str(k): cond.get(k, 0) for k in range(1, 7)},
                             "chi2": round(float(chi2), 4), "p_value": round(float(p), 6),
                             "tvd_from_uniform_1_6": round(cond_tvd, 5)},
        "acceptance_rate": round(accept, 5),
        "theoretical_acceptance": round((6 / 8) ** 2, 5),
    }
    with open(os.path.join(HERE, "ibm_experiment_results.json"), "w") as f:
        json.dump(res, f, indent=2)

    print("\n=== HARDWARE LATEX-READY NUMBERS ===")
    print(f"backend = {backend.name}, shots = {SHOTS}, job = {job_id}")
    print(f"raw 0..7 counts = {raw_counts},  TVD(raw,1/8) = {raw_tvd:.4f}")
    print(f"conditioned 1..6 counts = {cond_counts}")
    print(f"conditioned: chi^2 = {chi2:.2f}, p = {p:.4f}, TVD(1/6) = {cond_tvd:.4f}")
    print(f"acceptance = {accept:.4f} (theory 0.5625)")


if __name__ == "__main__":
    main()
