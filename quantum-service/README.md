# Quantum Tavla — Dice Microservice

Genuinely-quantum backgammon dice over HTTP. FastAPI + Qiskit. Each die comes from a
**Hadamard circuit** (3 qubits per die, measured, rejection-sampled to a fair 1–6).
The Android app (`com.ekatavla`) calls this for every roll, falling back to a local RNG
if the service is unreachable.

## API

| Endpoint | Returns |
|---|---|
| `GET /roll?backend=aer\|ibm&dice=2` | `{d1,d2,sum,dice,backend,backend_requested,job_id,timestamp,circuit,shots,fallback}` |
| `GET /health` | `{status,version,uptime_s}` |
| `GET /backends` | `{default,backends[],ibm_configured}` |

- `backend=aer` (default): Qiskit **Aer** simulator — fast, exact, genuinely quantum.
- `backend=ibm`: least-busy **real IBM Quantum** hardware via `qiskit-ibm-runtime`.
  Synchronous with an `IBM_TIMEOUT_S` cap; if the queue is slow it transparently falls
  back to Aer and sets `"fallback": true`, `"backend_requested": "ibm"`. Requires
  `IBM_QUANTUM_TOKEN` in the **server** env (never in the client/git).

## Run locally

```bash
cd quantum-service
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# optional: cp .env.example .env  and set IBM_QUANTUM_TOKEN
uvicorn app.main:app --reload --port 8000
curl "http://localhost:8000/roll?backend=aer"
pytest                     # fairness + contract tests (Aer only)
```

Android device → dev machine: `adb reverse tcp:8000 tcp:8000` then point
`QUANTUM_SERVICE_URL` at `http://localhost:8000/`.

## Deploy to Railway (Docker)

> The login + token steps are interactive — run them yourself.

1. `npm i -g @railway/cli && railway login`
2. New Project → Deploy from this repo → set **Root Directory = `quantum-service`**
   (Railway uses `Dockerfile`). Or `railway up` from this folder.
3. Variables: `IBM_QUANTUM_TOKEN=<your token>` (optionally `IBM_CHANNEL`, `IBM_INSTANCE`,
   `IBM_TIMEOUT_S=18`, `DEFAULT_BACKEND=aer`). `PORT` is provided by Railway.
4. Settings → Networking → **Generate Domain** → copy the `https://…up.railway.app` URL.
5. Smoke test: `curl https://<url>/health` and `curl "https://<url>/roll?backend=aer"`.
6. Put `<url>/` (trailing slash) into the app's `QUANTUM_SERVICE_URL` build config.

## Notes / limits
- Real-hardware rolls are best-effort: under queue load you transparently get Aer dice
  (flagged via `fallback`). The IBM Open plan has limited monthly QPU time — default to Aer.
- Free-tier cold starts hurt dice latency; prefer a plan that stays warm, and/or hit
  `/health` on app launch to pre-warm.
- Fairness lives in `app/dice.py` rejection sampling. Never replace it with `v % 6`.
