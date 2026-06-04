"""Backend runners: Aer simulator (default) and IBM Quantum hardware (optional).

IBM mode is synchronous with a wall-clock timeout and automatic fallback to Aer, so a
backgammon roll always returns a usable value quickly even when the IBM queue is long.
"""
import secrets
import time
from typing import List, Optional, Tuple

from . import config
from .dice import build_dice_circuit, pick_valid_dice

# Lazily-initialised singletons (import qiskit-aer / runtime only when first used).
_aer = None
_ibm_service = None


def _get_aer():
    global _aer
    if _aer is None:
        from qiskit_aer import AerSimulator
        _aer = AerSimulator()
    return _aer


def _roll_aer_dice(num_dice: int, shots: int) -> Tuple[List[int], int]:
    """Run the circuit on Aer, batching shots until a valid (all 1..6) shot appears."""
    sim = _get_aer()
    qc = build_dice_circuit(num_dice)
    total = 0
    for _ in range(4):  # astronomically unlikely to need >1 batch
        result = sim.run(qc, shots=shots, memory=True).result()
        memory = result.get_memory()  # list[str], one bitstring per shot
        total += shots
        dice = pick_valid_dice(memory, num_dice)
        if dice is not None:
            return dice, total
    # Last resort (never expected): classical secure RNG, still in-range.
    return [1 + secrets.randbelow(6) for _ in range(num_dice)], total


def roll_aer(num_dice: int = 2, shots: int = None) -> dict:
    shots = shots or config.DEFAULT_SHOTS
    dice, used = _roll_aer_dice(num_dice, shots)
    return {
        "dice": dice,
        "backend": "aer_simulator",
        "job_id": "aer-" + secrets.token_hex(4),
        "shots": used,
        "fallback": False,
    }


def _get_ibm_service():
    global _ibm_service
    if _ibm_service is None:
        from qiskit_ibm_runtime import QiskitRuntimeService
        kwargs = {"channel": config.IBM_CHANNEL, "token": config.IBM_QUANTUM_TOKEN}
        if config.IBM_INSTANCE:
            kwargs["instance"] = config.IBM_INSTANCE
        _ibm_service = QiskitRuntimeService(**kwargs)
    return _ibm_service


def _result_bitstrings(pub_result) -> List[str]:
    """Extract per-shot bitstrings from a SamplerV2 PubResult (classical register 'c')."""
    data = pub_result.data
    # Prefer the named register; fall back to the first BitArray available.
    bit_array = getattr(data, "c", None)
    if bit_array is None:
        for k in data.keys():
            bit_array = data[k]
            break
    return list(bit_array.get_bitstrings())


def roll_ibm(num_dice: int = 2, shots: int = None) -> dict:
    """Roll on the least-busy real backend; raise on any failure so the caller falls back."""
    shots = shots or config.DEFAULT_SHOTS
    from qiskit_ibm_runtime import SamplerV2
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

    service = _get_ibm_service()
    backend = service.least_busy(operational=True, simulator=False)
    qc = build_dice_circuit(num_dice)
    pm = generate_preset_pass_manager(optimization_level=1, backend=backend)
    isa = pm.run(qc)

    sampler = SamplerV2(mode=backend)
    job = sampler.run([isa], shots=shots)
    job.wait_for_final_state(timeout=config.IBM_TIMEOUT_S)  # raises on timeout
    if job.status() != "DONE" and str(job.status()) != "JobStatus.DONE":
        raise RuntimeError(f"IBM job not done: {job.status()}")

    memory = _result_bitstrings(job.result()[0])
    dice = pick_valid_dice(memory, num_dice)
    if dice is None:  # extraordinarily unlikely
        raise RuntimeError("no valid IBM shot")
    return {
        "dice": dice,
        "backend": backend.name,
        "job_id": job.job_id(),
        "shots": shots,
        "fallback": False,
    }


def roll(backend_requested: str, num_dice: int = 2, shots: int = None) -> dict:
    """Dispatch to Aer or IBM, with IBM degrading to Aer on any problem."""
    if backend_requested == "ibm":
        if not config.IBM_CONFIGURED:
            out = roll_aer(num_dice, shots)
            out["fallback"] = True
            return out
        try:
            return roll_ibm(num_dice, shots)
        except Exception:
            out = roll_aer(num_dice, shots)  # transparent fallback
            out["fallback"] = True
            return out
    return roll_aer(num_dice, shots)


def backends_info() -> dict:
    items = [{"id": "aer", "name": "aer_simulator", "available": True,
              "type": "simulator", "configured": True}]
    items.append({"id": "ibm", "name": "ibm_least_busy",
                  "available": config.IBM_CONFIGURED, "type": "hardware",
                  "configured": config.IBM_CONFIGURED})
    return {"default": config.DEFAULT_BACKEND, "backends": items,
            "ibm_configured": config.IBM_CONFIGURED}
