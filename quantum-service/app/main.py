"""FastAPI app exposing genuinely-quantum backgammon dice.

Endpoints:
  GET /roll?backend=aer|ibm   -> RollResponse
  GET /health                 -> HealthResponse
  GET /backends               -> BackendsResponse
"""
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__, backends, config
from .models import RollResponse

app = FastAPI(title="Quantum Tavla Dice", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # no secrets in responses; an app and a web client both call this
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

_START = time.monotonic()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _err(status: int, error: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": error, "detail": detail, "status": status})


@app.get("/health")
def health():
    return {"status": "ok", "version": __version__, "uptime_s": int(time.monotonic() - _START)}


@app.get("/backends")
def list_backends():
    return backends.backends_info()


@app.get("/roll", response_model=RollResponse)
@app.post("/roll", response_model=RollResponse)
def roll(backend: str = Query(default=None), dice: int = Query(default=2)):
    requested = (backend or config.DEFAULT_BACKEND).lower()
    if requested not in ("aer", "ibm"):
        return _err(400, "invalid_backend", "backend must be 'aer' or 'ibm'")
    if dice < 1 or dice > 4:
        return _err(400, "invalid_dice", "dice must be between 1 and 4")
    try:
        result = backends.roll(requested, num_dice=dice)
    except Exception as e:  # safety net — should not happen given internal fallback
        return _err(500, "internal", str(e))
    vals = result["dice"]
    return RollResponse(
        d1=vals[0], d2=vals[1] if len(vals) > 1 else vals[0],
        sum=sum(vals[:2]), dice=vals,
        backend=result["backend"], backend_requested=requested,
        job_id=result["job_id"], timestamp=_now_iso(),
        circuit="hadamard-6q", shots=result["shots"], fallback=result["fallback"],
    )
