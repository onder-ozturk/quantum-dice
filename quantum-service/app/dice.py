"""Hadamard quantum dice — circuit construction and fair (rejection-sampled) decoding.

Scheme ("hadamard-6q"): one fair die = 3 qubits, each put in superposition with H,
then measured -> a uniform integer in 0..7. Reject 0 and 7 and resample; the six
accepted outcomes {1..6} are exactly equiprobable (1/8 each, conditioned on
acceptance -> 1/6). NEVER use v % 6 (that double-counts two faces and biases the die).

Two dice -> 6 qubits in a single circuit. We run a BATCH of shots and pick the first
shot whose two 3-bit groups are both in 1..6, so a roll is exactly one job/circuit
execution on Aer or IBM (critical for keeping IBM-hardware mode responsive).
"""
from typing import List, Optional
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

QUBITS_PER_DIE = 3
CIRCUIT_ID = "hadamard-6q"


def build_dice_circuit(num_dice: int = 2) -> QuantumCircuit:
    n = QUBITS_PER_DIE * num_dice
    qr = QuantumRegister(n, "q")
    cr = ClassicalRegister(n, "c")  # named "c" so SamplerV2 result data is keyed predictably
    qc = QuantumCircuit(qr, cr)
    qc.h(qr)              # full uniform superposition over 2^n basis states
    qc.measure(qr, cr)
    return qc


def _decode_shot(bitstring: str, num_dice: int) -> List[int]:
    """Turn one measured bitstring into raw 0..7 values (pre-rejection)."""
    bits = bitstring.replace(" ", "")[::-1]  # normalize to qubit0..qubit(n-1) order
    out = []
    for i in range(num_dice):
        chunk = bits[i * QUBITS_PER_DIE:(i + 1) * QUBITS_PER_DIE]
        out.append(int(chunk[::-1], 2))      # 0..7; any consistent order is uniform
    return out


def pick_valid_dice(shots: List[str], num_dice: int = 2) -> Optional[List[int]]:
    """Return the first shot whose every die lands in 1..6, else None (caller re-batches)."""
    for bitstring in shots:
        dice = _decode_shot(bitstring, num_dice)
        if all(1 <= d <= 6 for d in dice):
            return dice
    return None
