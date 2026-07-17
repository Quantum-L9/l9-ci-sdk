"""Public gate evaluation API."""

from .evaluator import evaluate_gate
from .model import (
    GATE_RESULT_PROTOCOL,
    GATE_RESULT_SCHEMA_VERSION,
    GateResult,
    GateStatus,
)

__all__ = [
    "GATE_RESULT_PROTOCOL",
    "GATE_RESULT_SCHEMA_VERSION",
    "GateResult",
    "GateStatus",
    "evaluate_gate",
]
