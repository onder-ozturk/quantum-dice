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

# Path hack so the circuit figure can import the production dice builder.
# qiskit is imported lazily inside make_circuit_figure() so the other
# (pure-matplotlib) figures regenerate without a qiskit install.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'quantum-service')))

HERE = os.path.dirname(__file__)

def save_tight(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path, format="pdf", bbox_inches="tight", pad_inches=0.02, dpi=300)
    plt.close(fig)
    print(f"Saved {path}")
    return path

# 1. Circuit diagram for 6 qubits (H on all + measure)
def make_circuit_figure():
    from app.dice import build_dice_circuit  # lazy: only this figure needs qiskit
    qc = build_dice_circuit(2)  # exactly the production circuit
    # Make it nicer: add labels
    # qiskit draw mpl
    fig = qc.draw(output="mpl", style="iqp", initial_state=True, cregbundle=True)
    ax = fig.axes[0]
    # Die-group annotation is given in the LaTeX caption (q0-q2 = die 1, q3-q5 = die 2)
    # No internal title: the LaTeX \caption describes the circuit (avoids a title-over-caption duplicate).
    return save_tight(fig, "hadamard-6q-circuit.pdf")

# 2. Rejection sampling flow (simple box+arrow diagram)
def make_rejection_flow():
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

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
    # No internal title: the LaTeX \caption carries the chi^2/p/TVD numbers.
    ax.legend()
    ax.axhline(exp, color="gray", linestyle=":", linewidth=0.8)
    ax.set_ylim(0, max(counts)*1.15)

    # Add small residual labels
    for i,c in enumerate(counts):
        resid = c - exp
        ax.text(i, c + 120, f"{resid:+.0f}", ha="center", fontsize=7, color="dimgray")

    plt.tight_layout()
    return save_tight(fig, "aer-observed-frequencies.pdf")

# 5. Service-contract / architecture diagram (restrained single-accent palette)
def make_backend_diagram():
    fig, ax = plt.subplots(figsize=(9.5, 4.0))
    ax.set_xlim(0, 12)
    ax.set_ylim(2.6, 7.1)
    ax.axis("off")

    EDGE, MUTED, FILL, ACCENT = "#34495E", "#5D6D7E", "#F4F6F7", "#EAF2F8"

    def box(x, y, w, h, text, fill=FILL):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03",
                     facecolor=fill, edgecolor=EDGE, linewidth=1.0))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=8.5, color="#212F3D")

    def arrow(x0, y0, x1, y1, color=EDGE, lw=1.3, ls="-"):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, ls=ls))

    # Client -> service
    box(0.3, 4.5, 2.2, 1.8, "Android client\n(EkaTavla engine)\n\ncalls GET /roll")
    arrow(2.5, 5.4, 3.15, 5.4)

    # Service (the single accent box)
    box(3.2, 3.6, 2.8, 3.3,
        "Quantum dice service\n(FastAPI)\n\nbuild hadamard-6q\ndispatch Aer / IBM\npick_valid_dice\nprovenance + fallback",
        fill=ACCENT)

    # Backends
    box(6.8, 5.0, 2.4, 1.6, "Qiskit Aer\n(simulator)\nideal Born sampling")
    box(6.8, 3.0, 2.4, 1.6, "IBM Quantum\n(least-busy device)")
    arrow(6.0, 5.5, 6.8, 5.8, lw=1.1)
    arrow(6.0, 4.2, 6.8, 3.8, lw=1.1)
    ax.text(6.35, 4.85, "or", fontsize=7.5, color=MUTED, ha="center")

    # Fallback: on IBM timeout the service transparently returns an Aer result
    arrow(7.6, 4.6, 7.6, 5.0, color=MUTED, lw=1.0, ls="--")
    ax.text(8.3, 4.8, "fallback", fontsize=7.5, color=MUTED, ha="center",
            va="center", style="italic")

    # Result -> game engine
    arrow(9.2, 5.4, 10.5, 5.4)
    box(10.3, 4.5, 1.5, 1.8, "Game engine\n(classical roll)")

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


# 7. Multi-backend hardware run + M3 readout mitigation (only if results exist)
def make_mitigation_figure():
    json_path = os.path.join(HERE, "ibm_mitigation_results.json")
    if not os.path.exists(json_path):
        return None
    with open(json_path) as f:
        d = json.load(f)
    if d.get("status") != "done" or not d.get("backends"):
        return None
    backends = d["backends"]
    names = [b["backend"].replace("ibm_", "") for b in backends]
    colors = ["#2980B9", "#C0392B", "#8E44AD", "#27AE60"]

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))

    # Panel A: raw conditioned 1..6 distribution per backend vs ideal 1/6
    ax = axes[0]
    faces = np.arange(1, 7)
    width = 0.8 / len(backends)
    for i, b in enumerate(backends):
        dist = b["raw"]["dist_1to6"]
        ax.bar(faces + (i - (len(backends) - 1) / 2) * width, dist, width,
               label=names[i], color=colors[i % len(colors)], edgecolor="black", linewidth=0.4)
    ax.axhline(1 / 6, color="gray", linestyle="--", label="ideal 1/6")
    ax.set_xticks(faces); ax.set_xlabel("die face"); ax.set_ylabel("probability")
    ax.set_ylim(0, 0.22)
    ax.set_title("Raw conditioned $1$--$6$ distribution")
    ax.legend(fontsize=7)

    # Panel B: raw vs M3-mitigated TVD(1..6) per backend
    ax = axes[1]
    x = np.arange(len(backends))
    raw_tvd = [b["raw"]["tvd_1to6"] for b in backends]
    mit_tvd = [b["mitigated"]["tvd_1to6"] for b in backends]
    w = 0.35
    b1 = ax.bar(x - w / 2, raw_tvd, w, label="raw", color="#E67E22", edgecolor="black")
    b2 = ax.bar(x + w / 2, mit_tvd, w, label="M3-mitigated", color="#16A085", edgecolor="black")
    ax.set_xticks(x); ax.set_xticklabels(names)
    ax.set_ylabel("TVD from uniform $1/6$")
    ax.set_title("Readout-error mitigation (M3) effect")
    ax.legend(fontsize=8)
    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.0008,
                    f"{bar.get_height():.3f}", ha="center", fontsize=7)
    ax.set_ylim(0, max(raw_tvd + mit_tvd) * 1.3)

    fig.suptitle(f"Multi-backend hardware run ({d['shots']} shots each): device readout bias "
                 f"and its partial mitigation", fontsize=9)
    plt.tight_layout()
    return save_tight(fig, "ibm-mitigation.pdf")


# 8. Repeated multi-backend run: run-to-run TVD variance (box plot) + mean bias shape
def make_repeated_figure():
    json_path = os.path.join(HERE, "ibm_repeated_results.json")
    if not os.path.exists(json_path):
        return None
    with open(json_path) as f:
        d = json.load(f)
    if not d.get("backends"):
        return None
    backends = d["backends"]
    names = [b["backend"].replace("ibm_", "") for b in backends]
    n_runs = d.get("n_runs", "?")

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.9))

    # Panel A: box plot of raw vs mitigated TVD over the runs, per backend
    ax = axes[0]
    positions, box_data, box_colors, xticks, xticklabels = [], [], [], [], []
    pos = 1
    for i, b in enumerate(backends):
        raw = [r["raw_tvd_1to6"] for r in b["runs"]]
        mit = [r["mit_tvd_1to6"] for r in b["runs"]]
        positions += [pos, pos + 0.7]
        box_data += [raw, mit]
        box_colors += ["#E67E22", "#16A085"]
        xticks.append(pos + 0.35); xticklabels.append(names[i])
        pos += 2.0
    bp = ax.boxplot(box_data, positions=positions, widths=0.55, patch_artist=True,
                    showmeans=True, meanprops=dict(marker="D", markerfacecolor="white",
                    markeredgecolor="black", markersize=4))
    for patch, c in zip(bp["boxes"], box_colors):
        patch.set_facecolor(c); patch.set_alpha(0.65)
    # overlay individual run points
    for p, data, c in zip(positions, box_data, box_colors):
        ax.scatter(np.full(len(data), p) + np.linspace(-0.12, 0.12, len(data)),
                   data, color=c, edgecolor="black", linewidth=0.3, s=14, zorder=3)
    ax.set_xticks(xticks); ax.set_xticklabels(xticklabels)
    ax.set_ylabel("TVD from uniform $1/6$")
    ax.set_title(f"Run-to-run TVD ($N={n_runs}$ runs/backend)")
    ax.axhline(0, color="gray", lw=0.5)
    raw_patch = mpatches.Patch(color="#E67E22", alpha=0.65, label="raw")
    mit_patch = mpatches.Patch(color="#16A085", alpha=0.65, label="M3-mitigated")
    ax.legend(handles=[raw_patch, mit_patch], fontsize=8)

    # Panel B: mean conditioned 1..6 distribution per backend (avg over runs) vs ideal
    ax = axes[1]
    faces = np.arange(1, 7)
    width = 0.8 / len(backends)
    colors = ["#2980B9", "#C0392B", "#8E44AD", "#27AE60"]
    for i, b in enumerate(backends):
        dists = np.array([r["raw_dist_1to6"] for r in b["runs"]])
        mean = dists.mean(axis=0)
        std = dists.std(axis=0, ddof=1) if dists.shape[0] > 1 else np.zeros(6)
        ax.bar(faces + (i - (len(backends) - 1) / 2) * width, mean, width,
               yerr=std, capsize=2, label=names[i],
               color=colors[i % len(colors)], edgecolor="black", linewidth=0.4)
    ax.axhline(1 / 6, color="gray", linestyle="--", label="ideal 1/6")
    ax.set_xticks(faces); ax.set_xlabel("die face"); ax.set_ylabel("probability")
    ax.set_ylim(0, 0.22)
    ax.set_title("Mean raw $1$--$6$ distribution ($\\pm$ s.d.)")
    ax.legend(fontsize=7)

    plt.tight_layout()
    return save_tight(fig, "ibm-repeated.pdf")


def main():
    print("Generating figures (requires venv with qiskit + matplotlib)...")
    make_circuit_figure()
    make_rejection_flow()
    make_bias_comparison()
    make_observed_bars()
    make_backend_diagram()
    if make_ibm_figure():
        print("Generated ibm-vs-ideal.pdf from hardware results.")
    if make_mitigation_figure():
        print("Generated ibm-mitigation.pdf from multi-backend mitigation results.")
    if make_repeated_figure():
        print("Generated ibm-repeated.pdf from repeated multi-backend results.")
    print("All figures generated.")

if __name__ == "__main__":
    main()
