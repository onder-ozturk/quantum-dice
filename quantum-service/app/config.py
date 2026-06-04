"""Runtime configuration, sourced from environment variables only.

IBM_QUANTUM_TOKEN is read from the server environment exclusively — never from
the client, a response body, or version control.
"""
import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# IBM Quantum credentials (optional). When unset, only the Aer simulator is offered.
IBM_QUANTUM_TOKEN = os.environ.get("IBM_QUANTUM_TOKEN") or None
# Token channel: "ibm_quantum" (legacy) or "ibm_cloud" depending on the account.
IBM_CHANNEL = os.environ.get("IBM_CHANNEL", "ibm_quantum")
# Optional pinned instance "hub/group/project" for the legacy channel.
IBM_INSTANCE = os.environ.get("IBM_INSTANCE") or None

# Hard wall-clock cap (seconds) for a real-hardware job before we fall back to Aer.
IBM_TIMEOUT_S = _int("IBM_TIMEOUT_S", 18)

# Backend selected when the client does not pass ?backend=.
DEFAULT_BACKEND = os.environ.get("DEFAULT_BACKEND", "aer").lower()
# Shots run per roll (batched so rejection-sampling never loops; see dice.py).
DEFAULT_SHOTS = _int("DEFAULT_SHOTS", 64)

IBM_CONFIGURED = IBM_QUANTUM_TOKEN is not None
