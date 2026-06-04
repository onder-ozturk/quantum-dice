"""Pydantic response models — the single source of truth for the HTTP API contract.

The Android Moshi data classes mirror RollResponse field-for-field, so keep all
fields present and non-null on every success.
"""
from typing import List
from pydantic import BaseModel


class RollResponse(BaseModel):
    d1: int                 # first die, 1..6
    d2: int                 # second die, 1..6
    sum: int                # d1 + d2, 2..12
    dice: List[int]         # [d1, d2]
    backend: str            # actual backend that produced the result, e.g. "aer_simulator" / "ibm_brisbane"
    backend_requested: str  # what the client asked for: "aer" | "ibm"
    job_id: str             # opaque id (synthetic for Aer, Runtime job id for IBM)
    timestamp: str          # ISO-8601 UTC, Z-suffixed
    circuit: str            # "hadamard-6q"
    shots: int              # shots actually executed for this roll
    fallback: bool          # True when ibm was requested but Aer served the result


class BackendInfo(BaseModel):
    id: str
    name: str
    available: bool
    type: str
    configured: bool = True


class BackendsResponse(BaseModel):
    default: str
    backends: List[BackendInfo]
    ibm_configured: bool


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_s: int


class ErrorResponse(BaseModel):
    error: str
    detail: str
    status: int
