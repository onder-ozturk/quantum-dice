#!/usr/bin/env python3
"""
Generate all figures for the quantum dice paper.
Run under the quantum-service venv (see Makefile or README in paper).

Produces in this directory:
- hadamard-6q-circuit.pdf
- rejection-sampling-flow.pdf
- modulo-vs-rejection-bars.pdf
- aer-observed-frequencies.pdf
- backend-contract.pdf (simple architecture diagram)
"""

import os
import sys
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib

# Headless
matplotlib.use("Agg")

# Path hack for qiskit + dice
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'quantum-service')))

from qiskit import QuantumCircuit
from app.dice import build_dice_circuit

HERE = os.path.dirname(__file__)

def save_tight(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path, format="pdf", bbox_inches="tight", pad_inches=0.02, dpi=300)
    plt.close(fig)
    print(f"Saved {path}")
    return path

# 1. Circuit diagram for 6 qubits (H on all + measure)
def make_circuit_figure():
    qc = build_dice_circuit(2)  # exactly the production circuit
    # Make it nicer: add labels
    # qiskit draw mpl
    fig = qc.draw(output="mpl", style="iqp", initial_state=True, cregbundle=True)
    ax = fig.axes[0]
    # Die-group annotation is given in the LaTeX caption (q0-q2 = die 1, q3-q5 = die 2)
    # to avoid floating labels; only set a properly math-rendered title here.
    ax.set_title(r"hadamard-6q circuit: $H^{\otimes 6}$ then computational-basis measurement",
                 fontsize=10)
    return save_tight(fig, "hadamard-6q-circuit.pdf")

# 2. Rejection sampling flow (simple box+arrow diagram)
def make_rejection_flow():
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title("Rejection Sampling for Fair 1–6 Die (per shot in batch)", fontsize=11, pad=10)

    boxes = [
        (0.5, 4.5, "Measure 3 qubits\n→ raw X ∈ {0..7}"),
        (3.5, 4.5, "X ∈ {1,2,3,4,5,6} ?"),
        (6.5, 4.5, "Accept X as die face\n(D = X)"),
        (3.5, 2.0, "Reject (0 or 7)\n→ continue to next\nshot in batch"),
        (8.5, 2.0, "If batch exhausted\n(no valid shot)\n→ new batch or\nclassical fallback"),
    ]
    for x,y,text in boxes:
        box = FancyBboxPatch((x, y-0.7), 2.4, 1.4, boxstyle="round,pad=0.05", 
                             facecolor="#E8F4FD", edgecolor="#2E6DA4", linewidth=1.5)
        ax.add_patch(box)
        ax.text(x+1.2, y, text, ha="center", va="center", fontsize=8)

    # Arrows
    ax.annotate("", xy=(3.4,4.5), xytext=(2.9,4.5), arrowprops=dict(arrowstyle="->", color="#2E6DA4", lw=1.5))
    ax.annotate("", xy=(6.4,4.5), xytext=(5.9,4.5), arrowprops=dict(arrowstyle="->", color="#2E6DA4", lw=1.5))
    ax.annotate("yes", xy=(5.0,4.9), fontsize=8, color="green", fontweight="bold")
    ax.annotate("", xy=(4.7,2.7), xytext=(4.7,3.8), arrowprops=dict(arrowstyle="->", color="#C0392B", lw=1.5))
    ax.annotate("no", xy=(4.9,3.2), fontsize=8, color="#C0392B", fontweight="bold")
    ax.annotate("", xy=(7.3,2.0), xytext=(5.9,2.0), arrowprops=dict(arrowstyle="->", color="#555", lw=1))
    ax.text(6.6, 2.25, r"rare (prob $\sim 10^{-23}$)", fontsize=7, color="#555")

    ax.text(5, 0.5, "All accepted faces are exactly equiprobable (1/6) by conditional probability. See Proposition 1.",
            ha="center", fontsize=8, style="italic")
    return save_tight(fig, "rejection-sampling-flow.pdf")

# 3. Modulo bias vs Rejection (bar comparison)
def make_bias_comparison():
    faces = np.arange(1,7)
    # Theoretical modulo (X mod 6)+1 from uniform 0-7
    # 0,6 ->1 ; 1,7->2 ; 2->3 ; 3->4 ; 4->5 ; 5->6
    mod_probs = np.array([2/8, 2/8, 1/8, 1/8, 1/8, 1/8])
    rej_probs = np.array([1/6]*6)

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), sharey=True)

    # Modulo
    ax = axes[0]
    bars = ax.bar(faces, mod_probs, color="#E74C3C", edgecolor="black", width=0.7)
    ax.axhline(1/6, color="gray", linestyle="--", label="ideal 1/6")
    ax.set_xticks(faces)
    ax.set_xlabel("Die face")
    ax.set_ylabel("Probability")
    ax.set_title("Biased (X mod 6 + 1)")
    ax.set_ylim(0, 0.35)
    ax.legend(fontsize=8)
    for b,p in zip(bars, mod_probs):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.005, f"{p:.3f}", ha="center", fontsize=7)

    # Rejection
    ax = axes[1]
    bars = ax.bar(faces, rej_probs, color="#27AE60", edgecolor="black", width=0.7)
    ax.axhline(1/6, color="gray", linestyle="--", label="1/6")
    ax.set_xticks(faces)
    ax.set_xlabel("Die face")
    ax.set_title("Rejection sampling (our method)")
    ax.set_ylim(0, 0.35)
    ax.legend(fontsize=8)
    for b,p in zip(bars, rej_probs):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.005, f"{p:.3f}", ha="center", fontsize=7)

    fig.suptitle("Why modulo produces bias while rejection sampling does not (uniform 0–7 input)", fontsize=10)
    plt.tight_layout()
    return save_tight(fig, "modulo-vs-rejection-bars.pdf")

# 4. Aer observed frequencies vs expected (from the generated csv/json)
def make_observed_bars():
    json_path = os.path.join(HERE, "aer_experiment_results.json")
    with open(json_path) as f:
        data = json.load(f)

    counts = [data["marginal"]["counts"][str(k)] for k in range(1,7)]
    N_faces = 2 * data["observed"]["total_valid_rolls"]
    exp = N_faces / 6.0

    fig, ax = plt.subplots(figsize=(7, 3.8))
    faces = np.arange(1,7)
    x = np.arange(len(faces))
    width = 0.35

    bars1 = ax.bar(x - width/2, counts, width, label="Observed (Aer)", color="#3498DB", edgecolor="black")
    bars2 = ax.bar(x + width/2, [exp]*6, width, label=f"Expected ({exp:.1f})", color="#BDC3C7", edgecolor="black")

    ax.set_xticks(x)
    ax.set_xticklabels([str(f) for f in faces])
    ax.set_xlabel("Die face")
    ax.set_ylabel("Count (out of 100 000 faces)")
    ax.set_title(f"Aer simulator frequencies (N={data['observed']['total_valid_rolls']:,} rolls, 100k faces)\n"
                 f"χ² = {data['marginal']['chi2']:.2f}, p = {data['marginal']['p_value']:.4f}, TVD = {data['marginal']['tvd']:.4f}")
    ax.legend()
    ax.axhline(exp, color="gray", linestyle=":", linewidth=0.8)
    ax.set_ylim(0, max(counts)*1.15)

    # Add small residual labels
    for i,c in enumerate(counts):
        resid = c - exp
        ax.text(i, c + 120, f"{resid:+.0f}", ha="center", fontsize=7, color="dimgray")

    plt.tight_layout()
    return save_tight(fig, "aer-observed-frequencies.pdf")

# 5. Simple backend / service contract diagram
def make_backend_diagram():
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title("System Architecture and Mathematical Contract", fontsize=11)

    # Boxes
    def box(x, y, w, h, text, color="#F8F9FA", ec="#2C3E50"):
        b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03", facecolor=color, edgecolor=ec, linewidth=1.2)
        ax.add_patch(b)
        ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=8, wrap=True)

    # Left: client
    box(0.3, 4.5, 2.2, 1.8, "Android Client\n(EkaTavlaEngine)\n\nobserveDice(forced)\n→ Roll(d1,d2)", "#E8F8F5", "#1ABC9C")
    # Arrow
    ax.annotate("", xy=(3.0, 5.4), xytext=(2.5, 5.4), arrowprops=dict(arrowstyle="->", color="#1ABC9C", lw=1.5))
    ax.text(2.7, 5.7, "GET /roll?backend=aer|ibm", fontsize=7, color="#1ABC9C")

    # Service
    box(3.2, 3.5, 2.8, 3.5, "Quantum Dice Service\n(FastAPI)\n\n• /roll\n• build hadamard-6q\n• dispatch Aer / IBM\n• pick_valid_dice\n• fallback flag", "#FCF3CF", "#F39C12")

    # Aer
    box(6.8, 5.0, 2.4, 1.6, "Qiskit Aer\n(simulator)\nideal Born sampling", "#D5F5E3", "#27AE60")
    # IBM
    box(6.8, 3.0, 2.4, 1.6, "IBM Quantum\n(least-busy real)\n+ timeout fallback", "#FADBD8", "#E74C3C")

    # Arrows service to backends
    ax.annotate("", xy=(6.8,5.8), xytext=(6.0,5.5), arrowprops=dict(arrowstyle="->", color="#27AE60", lw=1.2))
    ax.annotate("", xy=(6.8,3.8), xytext=(6.0,4.2), arrowprops=dict(arrowstyle="->", color="#E74C3C", lw=1.2))
    ax.text(6.3, 4.9, "or", fontsize=7)

    # Fallback arrow
    ax.annotate("", xy=(6.8,3.8), xytext=(9.2,5.0), arrowprops=dict(arrowstyle="->", color="#E74C3C", lw=1.0, ls="--"))
    ax.text(8.3, 4.6, "timeout / error\n→ transparent Aer\n(fallback=true)", fontsize=6.5, color="#C0392B", ha="center")

    # Output
    ax.annotate("", xy=(10.5,5.4), xytext=(9.2,5.4), arrowprops=dict(arrowstyle="->", color="#2C3E50", lw=1.5))
    box(10.3, 4.5, 1.5, 1.8, "Game\nEngine\n(classic\nRoll)", "#EBF5FB", "#3498DB")

    # Bottom note
    ax.text(6, 1.5, "Key contract: The game engine receives only classical (d1,d2) ∈ {1..6}².\n"
                   "The same circuit + rejection sampling math is used for both Aer and IBM backends.\n"
                   "Mathematical fairness (Propositions 1–2) is independent of which backend ultimately produced the bits.",
            ha="center", fontsize=8, style="italic", 
            bbox=dict(boxstyle="round", facecolor="#F4F6F7", edgecolor="#BDC3C7", alpha=0.9))

    return save_tight(fig, "backend-contract.pdf")

# 6. Hardware vs ideal (only if a finished IBM run exists)
def make_ibm_figure():
    json_path = os.path.join(HERE, "ibm_experiment_results.json")
    if not os.path.exists(json_path):
        return None
    with open(json_path) as f:
        d = json.load(f)
    if d.get("status") != "done":
        return None

    raw = [d["raw_0to7"]["counts"][str(k)] for k in range(8)]
    n_raw = sum(raw)
    cond = [d["conditioned_1to6"]["counts"][str(k)] for k in range(1, 7)]
    n_cond = sum(cond)
    backend = d.get("backend", "ibm")
    shots = d.get("shots", 0)

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))
    # raw 0..7 vs ideal 1/8
    ax = axes[0]
    ax.bar(range(8), [c / n_raw for c in raw], color="#E67E22", edgecolor="black", width=0.7)
    ax.axhline(1/8, color="gray", linestyle="--", label="ideal 1/8")
    ax.set_xticks(range(8)); ax.set_xlabel("raw 3-bit value $X$"); ax.set_ylabel("probability")
    ax.set_title(f"Raw measured $0$--$7$ (TVD={d['raw_0to7']['tvd_from_uniform_1_8']:.3f})")
    ax.legend(fontsize=8)
    # conditioned 1..6 vs ideal 1/6
    ax = axes[1]
    ax.bar(range(1, 7), [c / n_cond for c in cond], color="#16A085", edgecolor="black", width=0.7)
    ax.axhline(1/6, color="gray", linestyle="--", label="ideal 1/6")
    ax.set_xticks(range(1, 7)); ax.set_xlabel("die face"); ax.set_ylabel("probability")
    ax.set_title(f"After rejection (TVD={d['conditioned_1to6']['tvd_from_uniform_1_6']:.3f})")
    ax.legend(fontsize=8)
    fig.suptitle(f"Preliminary hardware run on {backend} ({shots} shots): noise perturbs the raw "
                 f"distribution, and rejection inherits the residual bias", fontsize=9)
    plt.tight_layout()
    return save_tight(fig, "ibm-vs-ideal.pdf")


def main():
    print("Generating figures (requires venv with qiskit + matplotlib)...")
    make_circuit_figure()
    make_rejection_flow()
    make_bias_comparison()
    make_observed_bars()
    make_backend_diagram()
    if make_ibm_figure():
        print("Generated ibm-vs-ideal.pdf from hardware results.")
    print("All figures generated.")

if __name__ == "__main__":
    main()
