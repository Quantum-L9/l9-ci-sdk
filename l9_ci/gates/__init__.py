"""Public gate evaluation API."""

from .evaluator import evaluate_gate
from .model import (
    GATE_RESULT_PROTOCOL,
    GATE_RESULT_SCHEMA_VERSION,
    GateResult,
    GateStatus,
    ReasonCode,
    ReasonDetail,
)

__all__ = [
    "GATE_RESULT_PROTOCOL",
    "GATE_RESULT_SCHEMA_VERSION",
    "GateResult",
    "GateStatus",
    "ReasonCode",
    "ReasonDetail",
    "evaluate_gate",
]
