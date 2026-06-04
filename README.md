# Quantum Tavla Dice — Reproducibility Package

Code, data, and manuscript for **"Hadamard-Based Rejection Sampling for Fair Dice:
A Low-Depth Quantum Circuit Model for Tabletop Games"** (Ö. Öztürk, 2026).

Each die is encoded with three qubits; applying `H` to all of them gives a uniform
superposition over `0..7`, and **rejecting the outcomes 0 and 7** yields an exactly
uniform 1–6 die (`P=1/6` per face). Two dice use the six-qubit product circuit
`hadamard-6q`. The repository contains the exact production circuit, the rejection
post-processor, the reproducible experiments, and the manuscript.

## Layout
- `paper/` — LaTeX source (`paper.tex`), `references.bib`, `Makefile`, the compiled
  `paper.pdf`, and `figures/` (figure PDFs, generation scripts, and saved data).
- `quantum-service/` — the FastAPI + Qiskit dice micro-service the paper analyses
  (`app/dice.py` = circuit + rejection; `app/backends.py` = Aer / IBM runners).
- `paper/figures/` — `generate_experiments.py` (seeded Aer run), `generate_figures.py`,
  `run_ibm_experiment.py` (single-backend hardware) and `run_ibm_mitigated.py`
  (two-backend hardware with M3 readout-error mitigation), plus
  `aer_experiment_results.json`, `ibm_experiment_results.json`,
  `ibm_mitigation_results.json`, and CSVs.

See **[REPRODUCE.md](REPRODUCE.md)** for step-by-step reproduction. MIT licensed.

## Headline numbers
- **Aer (seeded, `seed_simulator=42`, bit-for-bit reproducible):** marginal
  χ²=10.13, p=0.072, TVD=0.0043; joint 6×6 χ²=26.85, p=0.84; raw acceptance 0.56344.
- **Real hardware (two 156-qubit IBM Heron devices, 4000 shots each):** post-rejection
  1–6 TVD = 0.019 (`ibm_marrakesh`) and 0.040 (`ibm_kingston`) from 1/6; M3 readout-error
  mitigation (`mthree`) brings both to TVD ≈ 0.021 — partially recoverable, percent-level
  device bias. (An earlier single-backend run on `ibm_marrakesh` gave raw 0–7 TVD=0.0102.)

No credentials are stored in this repository; the real-hardware run requires your own
IBM Quantum API key (see REPRODUCE.md).
