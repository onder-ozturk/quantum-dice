# Quantum Tavla Dice — Reproducibility Package

Code, data, and manuscript for **"Characterising Quantum Randomness under Classical
Rejection Sampling in Quantum-Backend-as-a-Service Architectures: A Readout-Mitigated
Hardware Study with a Fair-Dice Case Study"** (Ö. Öztürk, 2026). The fair-dice/Tavla
construction is the running case study; the contribution is a quantitative account of
how rejection-based classical post-processing transports quantum-hardware noise.

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
  `run_ibm_experiment.py` (single-backend hardware), `run_ibm_mitigated.py`
  (two-backend, M3 readout-error mitigation), and `run_ibm_repeated.py`
  (five-run, two-backend characterisation with run-to-run variance), plus
  `aer_experiment_results.json`, `ibm_experiment_results.json`,
  `ibm_mitigation_results.json`, `ibm_repeated_results.json`, and CSVs.

See **[REPRODUCE.md](REPRODUCE.md)** for step-by-step reproduction. MIT licensed.

## Headline numbers
- **Aer (seeded, `seed_simulator=42`, bit-for-bit reproducible):** marginal
  χ²=10.13, p=0.072, TVD=0.0043; joint 6×6 χ²=26.85, p=0.84; raw acceptance 0.56344.
- **Real hardware (two 156-qubit IBM Heron devices, five runs × 4000 shots each):**
  post-rejection 1–6 TVD = 0.015±0.006 (`ibm_marrakesh`) and 0.032±0.006 (`ibm_kingston`)
  from 1/6 (mean±s.d. over 5 runs); M3 readout-error mitigation (`mthree`) roughly halves
  the noisier device's bias (`ibm_kingston` → 0.014±0.004) but not the cleaner one
  (`ibm_marrakesh` → 0.017±0.008), where calibration noise dominates.
- **Theory + statistics:** a tight bound shows rejection sampling amplifies raw bias by at
  most 1/p(A) ≤ 4/3 (it cannot remove device bias); a χ² power analysis fixes the minimum
  detectable TVD per experiment, explaining every reported p-value.

No credentials are stored in this repository; the real-hardware run requires your own
IBM Quantum API key (see REPRODUCE.md).
