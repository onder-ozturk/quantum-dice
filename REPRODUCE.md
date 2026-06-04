# Reproducing the results

## 1. Environment
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r quantum-service/requirements.txt
pip install numpy scipy matplotlib
```
(Qiskit 1.x + qiskit-aer; qiskit-ibm-runtime is only needed for the optional hardware run.)

## 2. Aer simulator experiment (seeded, bit-for-bit reproducible)
```bash
PYTHONPATH=quantum-service python paper/figures/generate_experiments.py
```
Writes `paper/figures/aer_experiment_results.json`, `aer_marginal.csv`, `aer_joint.csv`.
With `seed_simulator=42` the output is identical on every run:
marginal χ²=10.13, p=0.072, TVD=0.0043; joint χ²=26.85, p=0.84; raw acceptance 0.56344.

## 3. Figures
```bash
PYTHONPATH=quantum-service python paper/figures/generate_figures.py
```
Regenerates all figure PDFs from the saved JSON/CSV (and `ibm-vs-ideal.pdf` if a finished
hardware result is present).

## 4. Build the manuscript
```bash
cd paper && make bib
```
Requires TeX Live with `lualatex`, `fontspec`, and Latin Modern (the paper uses fontspec).
Produces `paper/paper.pdf` (~11 pages).

## 5. Optional: real IBM-hardware run
You need your own **IBM Quantum Platform** account (free Open plan is enough — a few
seconds of QPU time) and its **API key**. Never commit the key.
```bash
export IBM_QUANTUM_TOKEN=<your IBM Cloud API key>
export IBM_CHANNEL=ibm_cloud            # new IBM Quantum Platform
# export IBM_INSTANCE=<crn:...>         # optional; auto-selected for a single Open instance
PYTHONPATH=quantum-service python paper/figures/run_ibm_experiment.py
```
Runs the exact `hadamard-6q` circuit on the least-busy real backend (4000 shots by default),
writes `paper/figures/ibm_experiment_results.json`, then re-run step 3 to regenerate
`ibm-vs-ideal.pdf`. The reported run used `ibm_marrakesh` (raw 0–7 TVD=0.0102, post-rejection
1–6 TVD=0.0184); your numbers will differ by device, calibration, and run.
