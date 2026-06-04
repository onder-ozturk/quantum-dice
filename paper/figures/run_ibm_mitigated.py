#!/usr/bin/env python3
"""
Readout-error-mitigated REAL-HARDWARE run of the hadamard-6q dice circuit on
TWO independent IBM Quantum backends.

For each backend we (a) run the exact production circuit (app.dice.build_dice_circuit(2)),
(b) measure the raw, *unmitigated* 0..7 and rejection-conditioned 1..6 distributions,
and (c) apply M3 matrix-free measurement (readout) error mitigation [Nation et al.,
PRX Quantum 2021] via the `mthree` package, then recompute the same distributions from
the mitigated quasiprobabilities. This isolates how much of the observed bias is
*readout* error (removable) versus deeper gate/decoherence error (not removable here).

Credentials come from the environment / .env (NEVER hard-coded):
    IBM_QUANTUM_TOKEN   (required)
    IBM_CHANNEL         (default: ibm_cloud)
    IBM_INSTANCE        (optional CRN)

Writes figures/ibm_mitigation_results.json and prints LaTeX-ready numbers.
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
CAL_SHOTS = int(os.environ.get("IBM_CAL_SHOTS", "4000"))
TIMEOUT_S = int(os.environ.get("IBM_RESULT_TIMEOUT_S", "1800"))
N_BACKENDS = int(os.environ.get("IBM_N_BACKENDS", "2"))


def load_env(path):
    """Minimal .env loader (does not overwrite already-set env vars).

    Supports both KEY=VALUE lines and a JSON blob like {"apikey": "..."} which is
    how IBM Quantum Platform hands out the API key file.
    """
    if not os.path.exists(path):
        return
    raw = open(path).read()
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            blob = json.loads(stripped)
            key = blob.get("apikey") or blob.get("token") or blob.get("IBM_QUANTUM_TOKEN")
            if key and not os.environ.get("IBM_QUANTUM_TOKEN"):
                os.environ["IBM_QUANTUM_TOKEN"] = key
            crn = blob.get("crn") or blob.get("instance")
            if crn and not os.environ.get("IBM_INSTANCE"):
                os.environ["IBM_INSTANCE"] = crn
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


def counts_to_distributions(counts):
    """Given a dict {bitstring: weight} (weight = shot count or quasiprob),
    return (raw_prob[0..7], cond_prob[1..6], acceptance) all as numpy arrays/floats.

    Each shot/mass contributes TWO die values (one per 3-qubit group), so raw mass
    totals 2*sum(weight); we normalise so raw_prob and cond_prob are proper
    distributions and acceptance is the pair-acceptance probability.
    """
    raw_mass = np.zeros(8)
    cond_mass = np.zeros(6)
    total_w = 0.0
    accept_w = 0.0
    for bs, w in counts.items():
        d1, d2 = _decode_shot(bs, 2)
        raw_mass[d1] += w
        raw_mass[d2] += w
        total_w += w
        if 1 <= d1 <= 6 and 1 <= d2 <= 6:
            accept_w += w
            cond_mass[d1 - 1] += w
            cond_mass[d2 - 1] += w
    raw_prob = raw_mass / (2.0 * total_w)
    cond_prob = cond_mass / cond_mass.sum() if cond_mass.sum() > 0 else cond_mass
    acceptance = accept_w / total_w if total_w else 0.0
    return raw_prob, cond_prob, acceptance


def tvd(prob, uniform):
    return float(0.5 * np.sum(np.abs(prob - uniform)))


def analyse_backend(service, backend, SamplerV2, generate_preset_pass_manager,
                    final_measurement_mapping, M3Mitigation):
    name = backend.name
    print(f"\n--- {name} ({backend.num_qubits} qubits) ---")
    qc = build_dice_circuit(2)
    try:
        pm = generate_preset_pass_manager(optimization_level=1, backend=backend,
                                          translation_method="translator")
    except Exception:
        pm = generate_preset_pass_manager(optimization_level=1, backend=backend)
    isa = pm.run(qc)
    mapping = final_measurement_mapping(isa)   # {clbit: physical_qubit}
    print(f"measurement mapping (clbit->qubit): {mapping}")

    sampler = SamplerV2(mode=backend)
    job = sampler.run([isa], shots=SHOTS)
    jid = job.job_id()
    print(f"submitted sampler job {jid} ({SHOTS} shots); waiting (timeout {TIMEOUT_S}s)...")
    job.wait_for_final_state(timeout=TIMEOUT_S)
    counts = job.result()[0].data.c.get_counts()
    print(f"got {sum(counts.values())} shots.")

    # --- raw (unmitigated) ---
    raw_p, cond_p, accept = counts_to_distributions(counts)
    u8, u6 = np.full(8, 1 / 8), np.full(6, 1 / 6)
    raw_tvd = tvd(raw_p, u8)
    cond_tvd = tvd(cond_p, u6)
    cond_counts = (cond_p * (accept * 2 * SHOTS)).round().astype(int)
    chi2, p = stats.chisquare(cond_counts, np.full(6, cond_counts.sum() / 6.0))

    # --- M3 readout mitigation ---
    print(f"calibrating M3 readout mitigation (cal shots={CAL_SHOTS})...")
    mit = M3Mitigation(backend)
    mit.cals_from_system(mapping, shots=CAL_SHOTS)
    quasi = mit.apply_correction(counts, mapping)
    mprob = quasi.nearest_probability_distribution()  # dict {bitstring: prob}
    mraw_p, mcond_p, maccept = counts_to_distributions(mprob)
    mraw_tvd = tvd(mraw_p, u8)
    mcond_tvd = tvd(mcond_p, u6)

    print(f"raw      : TVD(0..7)={raw_tvd:.4f}  TVD(1..6)={cond_tvd:.4f}  "
          f"chi2={chi2:.2f} p={p:.3f} accept={accept:.4f}")
    print(f"mitigated: TVD(0..7)={mraw_tvd:.4f}  TVD(1..6)={mcond_tvd:.4f}  "
          f"accept={maccept:.4f}")

    return {
        "backend": name,
        "num_qubits": int(backend.num_qubits),
        "job_id": jid,
        "shots": SHOTS,
        "cal_shots": CAL_SHOTS,
        "measurement_mapping": {str(k): int(v) for k, v in dict(mapping).items()},
        "raw": {
            "dist_0to7": [round(float(x), 5) for x in raw_p],
            "dist_1to6": [round(float(x), 5) for x in cond_p],
            "tvd_0to7": round(raw_tvd, 5),
            "tvd_1to6": round(cond_tvd, 5),
            "chi2": round(float(chi2), 4),
            "p_value": round(float(p), 6),
            "acceptance": round(accept, 5),
        },
        "mitigated": {
            "dist_0to7": [round(float(x), 5) for x in mraw_p],
            "dist_1to6": [round(float(x), 5) for x in mcond_p],
            "tvd_0to7": round(mraw_tvd, 5),
            "tvd_1to6": round(mcond_tvd, 5),
            "acceptance": round(maccept, 5),
        },
    }


def main():
    load_env(os.path.join(HERE, "..", ".env"))
    load_env(os.path.join(QSVC, ".env"))
    token = os.environ.get("IBM_QUANTUM_TOKEN")
    if not token:
        sys.exit("ERROR: IBM_QUANTUM_TOKEN not set (put it in .env or export it).")
    channel = os.environ.get("IBM_CHANNEL", "ibm_cloud")
    instance = os.environ.get("IBM_INSTANCE") or None

    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from mthree import M3Mitigation
    from mthree.utils import final_measurement_mapping

    print(f"Connecting to IBM Quantum (channel={channel})...")
    kwargs = {"channel": channel, "token": token}
    if instance:
        kwargs["instance"] = instance
    service = None
    last_err = None
    for attempt in range(4):
        try:
            service = QiskitRuntimeService(**kwargs)
            break
        except Exception as e:
            last_err = e
    if service is None:
        sys.exit(f"ERROR: could not init QiskitRuntimeService ({last_err}).")

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
            chosen.append(b)
            seen.add(b.name)
        if len(chosen) >= N_BACKENDS:
            break
    print("Chosen backends:", [b.name for b in chosen])

    results = []
    for b in chosen:
        try:
            results.append(analyse_backend(service, b, SamplerV2,
                                           generate_preset_pass_manager,
                                           final_measurement_mapping, M3Mitigation))
            # save incrementally so a later failure does not lose earlier data
            out = {"status": "partial" if len(results) < len(chosen) else "done",
                   "timestamp": datetime.now(timezone.utc).isoformat(),
                   "circuit": "hadamard-6q", "shots": SHOTS,
                   "mitigation": "M3 (mthree) matrix-free readout mitigation",
                   "backends": results}
            with open(os.path.join(HERE, "ibm_mitigation_results.json"), "w") as f:
                json.dump(out, f, indent=2, default=float)  # default=float: coerce numpy scalars
        except Exception as e:
            print(f"!! backend {b.name} failed: {e}")

    # final authoritative save (guards against a mid-loop save failure)
    out = {"status": "done", "timestamp": datetime.now(timezone.utc).isoformat(),
           "circuit": "hadamard-6q", "shots": SHOTS,
           "mitigation": "M3 (mthree) matrix-free readout mitigation", "backends": results}
    with open(os.path.join(HERE, "ibm_mitigation_results.json"), "w") as f:
        json.dump(out, f, indent=2, default=float)

    print("\n=== SUMMARY (LaTeX-ready) ===")
    for r in results:
        rr, mm = r["raw"], r["mitigated"]
        print(f"{r['backend']}: raw TVD(1..6)={rr['tvd_1to6']:.4f} -> "
              f"mitigated TVD(1..6)={mm['tvd_1to6']:.4f}  "
              f"(raw TVD(0..7)={rr['tvd_0to7']:.4f} -> {mm['tvd_0to7']:.4f})")
    print(f"\nSaved {os.path.join(HERE, 'ibm_mitigation_results.json')}")


if __name__ == "__main__":
    main()
