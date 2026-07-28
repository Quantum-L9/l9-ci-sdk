<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

## Decision locked

`l9ci.signals` is owned by **l9-ci-sdk**, as a new top-level contract package peer to `l9ci.contracts`. Producers import the schema; the SDK imports no producer, so none of the four forbidden edges (`SDK→Core`, `SDK→LSP`, `SDK→Repair`, `SDK→Corpus`) is created. The Core pin `f88116503430aa18992b70d8d31063e34ff97ef1` is untouched by every item below.[^1]

The l9-assurance repository is now inspected, which closes U-2 and materially changes F-8 — and surfaces three new blocking contradictions that were previously invisible.

## What Assurance actually is

Assurance is not a stub. It ships a Release-zero protocol with 18 versioned schemas, a registry of checks/claims/controls/producers/profiles, a `pull-request` profile binding seven controls, canonical JSON `l9.canonical-json/v1`, sha256 digests, a fail-closed single ingress at `l9assurance.cli.app.run_cli`, and a nine-value exit-code contract (`pass 0`, `conditional 10`, `fail 20`, `indeterminate 30`, `input 40`, `policy 41`, `admission 42`, `signature 43`, `invariant 50`).[^2]

That is a real decider. F-8 is therefore not "Assurance is undefined" — it is "two implemented verdict producers exist." The resolution direction from the prior pass stands: **Core publishes, Assurance decides**.

## Three new blocking findings

| ID | Finding | Evidence | Blocks |
| :-- | :-- | :-- | :-- |
| F-11 | Assurance's check registry names six checks owned by `l9-ci-sdk` — `l9.repository-metadata`, `l9.transport-packet`, `l9.sdk-validation`, `l9.lint`, `l9.tests`, `l9.mandatory-findings` [^2] — but the SDK's authoritative CLI exposes only `semgrep normalize`, `bundle validate`, `bundle project-agent-payload`, `compatibility check` [^1] | Registry asserts capabilities the owner does not implement | Loop 4 |
| F-12 | Assurance consumes `l9.observation/v1`; the SDK produces `l9.finding-bundle/v1`. No adapter exists in either repo [^2][^1] | Two canonical artifact shapes, zero bridge | Loop 4 |
| F-13 | Assurance's producer registry lists `l9-ci-sdk` with `authorizationStatus: pending`, `allowedVersions: null`, `candidateVersionRange >=2.0.0 <3.0.0`, `unknownReference UNKNOWN-001`; SDK's `.l9/integration-contract.yaml` declares `metadata.version 1.0.0` [^2][^1] | Untrusted producer + version range mismatch ⇒ every decision resolves `indeterminate` under `unknownHandling.mandatory: indeterminate` | Loop 4 |

F-13 is the sharpest: the org-default policy carries `l9.policy.trust-status: development-unactivated`. Assurance is wired to fail closed and currently *will*, on every subject, because its only producer is untrusted. That is correct behavior, not a defect — but it means Loop 4 cannot be scheduled until P-501 below lands.[^2]

## Architecture and reuse boundaries

| Plane | Repo | Owns | Must not own |
| :-- | :-- | :-- | :-- |
| Control | l9-ci-core | reusable workflows, global config, profiles, routing, publication [^3] | provider parsing, finding semantics, gate computation |
| Semantic | l9-ci-sdk | canonical contracts, provider SPI, normalization, deterministic serialization, redaction, **signal packet** [^1] | orchestration, artifact upload, org policy |
| Assurance | l9-assurance | evidence admission, control evaluation, verdict issuance [^2] | analysis semantics, mutation, corpus |
| Learning | l9-ci-debt-intelligence | corpus, recurrence, rule compilation, signed pack publication [^4] | pack activation, blocking policy mutation |
| Repair | PR_Repair | patch actuation, verification, rollback | diagnosis authority, policy promotion |

`l9ci.signals` sits in the semantic plane with a deliberately minimal dependency set: `contracts` only. It does **not** depend on `providers`, `policy`, `gates`, `pipeline`, or `integration`, which keeps it importable by any producer without dragging the analysis stack along.

## File tree

```
l9-ci-sdk/
├── l9ci/
│   ├── __init__.py                                      MODIFY  (version 1.0.0 -> 1.1.0)
│   ├── signals/                                         CREATE
│   │   ├── __init__.py                                  CREATE
│   │   ├── model.py                                     CREATE
│   │   ├── scoring.py                                   CREATE
│   │   ├── serialize.py                                 CREATE
│   │   └── validate.py                                  CREATE
│   └── schemas/v1/
│       ├── signal.schema.json                           CREATE
│       ├── signal-packet.schema.json                    CREATE
│       └── (10 existing schemas)                        RETAIN
├── tests/
│   ├── architecture/test_schema_inventory.py            MODIFY  (exact-equality set)
│   ├── architecture/test_public_api.py                  MODIFY  (add signals surface)
│   ├── architecture/test_dependency_boundaries.py       MODIFY  (add signals edges)
│   └── signals/                                         CREATE
│       ├── __init__.py                                  CREATE
│       ├── test_scoring.py                              CREATE
│       ├── test_determinism.py                          CREATE
│       └── test_schema_conformance.py                   CREATE
├── .l9/architecture.yaml                                MODIFY  (signals layer + edges)
├── .l9/ownership.yaml                                   MODIFY  (l9ci.signals owns)
├── .l9/integration-contract.yaml                        MODIFY  (version 1.1.0)
├── .l9/compatibility.yaml                               RETAIN
├── requirements.txt                                     RETAIN  (no new runtime dep)
└── .github/workflows/l9-analysis.yml                    RETAIN  (pin untouched)
```

Three test files are **modified, not appended to** — `test_schema_inventory.py` asserts exact set equality on `l9ci/schemas/v1/*.schema.json`, so adding two schemas breaks it unless `EXPECTED_SCHEMAS` is updated in the same commit.[^1]

## Complete implementation

### `l9ci/schemas/v1/signal.schema.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.quantum-l9.dev/l9-ci-sdk/v1/signal.schema.json",
  "title": "Signal",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "signal_id",
    "signal_type",
    "source_evidence",
    "confidence",
    "recurrence",
    "dimensions",
    "promotion_score_hundredths",
    "promotion_decision",
    "target_loop",
    "expected_behavior_change",
    "owner",
    "next_action",
    "limitations"
  ],
  "properties": {
    "signal_id": {
      "type": "string",
      "pattern": "^sig:[0-9a-f]{64}$"
    },
    "signal_type": {
      "enum": [
        "architecture_boundary_signal",
        "capability_signal",
        "configuration_signal",
        "dependency_signal",
        "finding_signal",
        "failure_fingerprint_signal",
        "validation_signal",
        "assurance_signal",
        "policy_signal",
        "repair_signal",
        "rollback_signal",
        "regression_signal",
        "recurrence_signal",
        "effectiveness_signal",
        "drift_signal",
        "operator_correction_signal",
        "friction_signal",
        "load_signal",
        "artifact_lineage_signal",
        "compatibility_signal",
        "mesh_edge_signal",
        "unknown_signal",
        "next_action_signal"
      ]
    },
    "source_evidence": {
      "type": "array",
      "minItems": 1,
      "uniqueItems": true,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["kind", "reference", "digest"],
        "properties": {
          "kind": {
            "enum": [
              "finding_bundle",
              "gate_result",
              "agent_review_payload",
              "provider_failure",
              "coverage",
              "workflow_run",
              "repair_attempt",
              "assurance_decision",
              "operator_action",
              "unknown"
            ]
          },
          "reference": { "type": "string", "minLength": 1 },
          "digest": { "type": "string", "pattern": "^[0-9a-f]{64}$" }
        }
      }
    },
    "confidence": { "enum": ["high", "medium", "low", "unknown"] },
    "recurrence": {
      "type": "object",
      "additionalProperties": false,
      "required": ["fingerprint", "observed_count"],
      "properties": {
        "fingerprint": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
        "observed_count": { "type": "integer", "minimum": 1 },
        "distinct_scope_count": { "type": "integer", "minimum": 1 }
      }
    },
    "dimensions": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "autonomy_gain",
        "future_reuse",
        "recurrence_prevention",
        "compounding_leverage",
        "proof_gain",
        "boundary_clarity",
        "friction_reduction",
        "load_reduction",
        "reversibility",
        "evidence_confidence",
        "complexity_cost",
        "runtime_coupling",
        "blast_radius_increase",
        "authority_ambiguity",
        "noise_risk"
      ],
      "properties": {
        "autonomy_gain": { "$ref": "#/$defs/score" },
        "future_reuse": { "$ref": "#/$defs/score" },
        "recurrence_prevention": { "$ref": "#/$defs/score" },
        "compounding_leverage": { "$ref": "#/$defs/score" },
        "proof_gain": { "$ref": "#/$defs/score" },
        "boundary_clarity": { "$ref": "#/$defs/score" },
        "friction_reduction": { "$ref": "#/$defs/score" },
        "load_reduction": { "$ref": "#/$defs/score" },
        "reversibility": { "$ref": "#/$defs/score" },
        "evidence_confidence": { "$ref": "#/$defs/score" },
        "complexity_cost": { "$ref": "#/$defs/score" },
        "runtime_coupling": { "$ref": "#/$defs/score" },
        "blast_radius_increase": { "$ref": "#/$defs/score" },
        "authority_ambiguity": { "$ref": "#/$defs/score" },
        "noise_risk": { "$ref": "#/$defs/score" }
      }
    },
    "downstream_reach": { "type": "integer", "minimum": 0 },
    "promotion_score_hundredths": {
      "type": "integer",
      "minimum": 0,
      "maximum": 10000
    },
    "promotion_decision": {
      "enum": ["promote", "defer", "evidence_only", "reject"]
    },
    "prohibited_risk": {
      "type": "array",
      "uniqueItems": true,
      "items": {
        "enum": [
          "authority_ambiguity",
          "blast_radius_unbounded",
          "irreversible_mutation",
          "unverified_evidence",
          "protected_path_touch"
        ]
      }
    },
    "target_loop": {
      "type": ["string", "null"],
      "minLength": 1
    },
    "expected_behavior_change": { "type": "string", "minLength": 1 },
    "owner": { "type": "string", "minLength": 1 },
    "next_action": { "type": ["string", "null"], "minLength": 1 },
    "limitations": {
      "type": "array",
      "uniqueItems": true,
      "items": { "type": "string", "minLength": 1 }
    }
  },
  "allOf": [
    {
      "if": { "properties": { "promotion_decision": { "const": "promote" } } },
      "then": { "required": ["target_loop", "next_action"] }
    }
  ],
  "$defs": {
    "score": { "type": "integer", "minimum": 0, "maximum": 5 }
  }
}
```


### `l9ci/schemas/v1/signal-packet.schema.json`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.quantum-l9.dev/l9-ci-sdk/v1/signal-packet.schema.json",
  "title": "SignalPacket",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "$schema_id",
    "schema_version",
    "sdk_version",
    "packet_id",
    "root_execution_id",
    "source_execution_id",
    "parent_execution_id",
    "source_repository",
    "source_revision",
    "subject_identity",
    "producer_identity",
    "workflow_identity",
    "configuration_digest",
    "dependency_manifest_digest",
    "input_artifact_digests",
    "extracted_signals",
    "promotion_decisions",
    "rejected_noise",
    "routed_loops",
    "unresolved_unknowns",
    "next_actions",
    "artifact_lineage",
    "validation_status",
    "limitations"
  ],
  "properties": {
    "$schema_id": { "const": "l9.signal-packet/v1" },
    "schema_version": { "type": "string", "pattern": "^1\\.[0-9]+\\.[0-9]+$" },
    "sdk_version": { "type": "string", "minLength": 1 },
    "packet_id": { "type": "string", "pattern": "^pkt:[0-9a-f]{64}$" },
    "root_execution_id": { "type": "string", "minLength": 1 },
    "source_execution_id": { "type": "string", "minLength": 1 },
    "parent_execution_id": { "type": ["string", "null"], "minLength": 1 },
    "source_repository": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"
    },
    "source_revision": {
      "type": "object",
      "additionalProperties": false,
      "required": ["commit", "dirty"],
      "properties": {
        "commit": { "type": ["string", "null"], "pattern": "^[0-9a-f]{40}$" },
        "dirty": { "type": "boolean" }
      }
    },
    "subject_identity": {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "value"],
      "properties": {
        "kind": {
          "enum": ["git_revision", "snapshot", "pull_request", "release_tag", "unknown"]
        },
        "value": { "type": "string", "minLength": 1 }
      }
    },
    "producer_identity": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "version"],
      "properties": {
        "id": {
          "enum": [
            "Quantum-L9/l9-ci-core",
            "Quantum-L9/l9-ci-sdk",
            "Quantum-L9/l9-ci-debt-resolver",
            "Quantum-L9/l9-ci-debt-intelligence",
            "Quantum-L9/l9-ci-debt-lsp",
            "Quantum-L9/l9-assurance",
            "Quantum-L9/l9-harness",
            "Quantum-L9/PR_Repair"
          ]
        },
        "version": { "type": "string", "minLength": 1 },
        "build_digest": { "type": "string", "pattern": "^[0-9a-f]{64}$" }
      }
    },
    "workflow_identity": {
      "type": "object",
      "additionalProperties": false,
      "required": ["workflow", "profile"],
      "properties": {
        "workflow": { "type": "string", "minLength": 1 },
        "profile": {
          "enum": ["pr_fast", "merge", "nightly", "release", "supply_chain", "unknown"]
        },
        "attempt": { "type": "integer", "minimum": 1 }
      }
    },
    "configuration_digest": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
    "dependency_manifest_digest": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
    "input_artifact_digests": {
      "type": "object",
      "additionalProperties": { "type": "string", "pattern": "^[0-9a-f]{64}$" }
    },
    "extracted_signals": {
      "type": "array",
      "items": { "$ref": "signal.schema.json" }
    },
    "promotion_decisions": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["signal_id", "decision", "reasons"],
        "properties": {
          "signal_id": { "type": "string", "pattern": "^sig:[0-9a-f]{64}$" },
          "decision": { "enum": ["promote", "defer", "evidence_only", "reject"] },
          "reasons": {
            "type": "array",
            "minItems": 1,
            "items": { "type": "string", "minLength": 1 }
          }
        }
      }
    },
    "rejected_noise": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["signal_id", "reason"],
        "properties": {
          "signal_id": { "type": "string", "pattern": "^sig:[0-9a-f]{64}$" },
          "reason": {
            "enum": [
              "no_named_consumer",
              "no_behavior_change",
              "score_below_threshold",
              "prohibited_risk",
              "duplicate_fingerprint",
              "insufficient_evidence"
            ]
          }
        }
      }
    },
    "routed_loops": {
      "type": "array",
      "uniqueItems": true,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["loop_id", "generation", "idempotency_key"],
        "properties": {
          "loop_id": { "type": "string", "minLength": 1 },
          "generation": { "type": "integer", "minimum": 0, "maximum": 8 },
          "idempotency_key": { "type": "string", "pattern": "^[0-9a-f]{64}$" }
        }
      }
    },
    "unresolved_unknowns": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["unknown_id", "category", "description", "impact"],
        "properties": {
          "unknown_id": { "type": "string", "minLength": 1 },
          "category": {
            "enum": [
              "missing_evidence",
              "invalid_evidence",
              "stale_evidence",
              "unsupported_check",
              "unverified_producer",
              "policy_ambiguity",
              "environment_uncertainty",
              "external_dependency",
              "other"
            ]
          },
          "description": { "type": "string", "minLength": 1 },
          "impact": { "enum": ["none", "advisory", "control", "decision"] }
        }
      }
    },
    "next_actions": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["action", "owner", "blocking"],
        "properties": {
          "action": { "type": "string", "minLength": 1 },
          "owner": { "type": "string", "minLength": 1 },
          "blocking": { "type": "boolean" }
        }
      }
    },
    "artifact_lineage": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["artifact", "digest", "role"],
        "properties": {
          "artifact": { "type": "string", "minLength": 1 },
          "digest": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
          "role": { "enum": ["input", "output", "derived"] }
        }
      }
    },
    "validation_status": {
      "enum": ["valid", "invalid", "incomplete", "unknown"]
    },
    "limitations": {
      "type": "array",
      "uniqueItems": true,
      "items": { "type": "string", "minLength": 1 }
    }
  }
}
```


### `l9ci/signals/__init__.py`

```python
"""Canonical L9 signal packet contracts.

This package owns the signal-packet artifact contract. It depends only on
``l9ci.contracts`` and the Python standard library. It must never import
providers, policy, gates, pipeline, or integration, and it must never import
any consumer repository.
"""

from __future__ import annotations

from .model import (
    ArtifactLineageEntry,
    EvidenceReference,
    NextAction,
    ProducerIdentity,
    PromotionDecision,
    RejectedNoise,
    RoutedLoop,
    Signal,
    SignalDimensions,
    SignalPacket,
    SignalType,
    SourceRevision,
    SubjectIdentity,
    UnresolvedUnknown,
    ValidationStatus,
    WorkflowIdentity,
)
from .scoring import (
    NEGATIVE_WEIGHTS,
    POSITIVE_WEIGHTS,
    PROHIBITED_RISKS,
    decide,
    max_raw_score,
    promotion_score_hundredths,
)
from .serialize import canonical_bytes, packet_id, signal_id, write_packet_atomic
from .validate import (
    SignalContractError,
    load_and_validate_packet,
    validate_packet,
    validate_packet_semantics,
)

__all__ = [
    "NEGATIVE_WEIGHTS",
    "POSITIVE_WEIGHTS",
    "PROHIBITED_RISKS",
    "ArtifactLineageEntry",
    "EvidenceReference",
    "NextAction",
    "ProducerIdentity",
    "PromotionDecision",
    "RejectedNoise",
    "RoutedLoop",
    "Signal",
    "SignalContractError",
    "SignalDimensions",
    "SignalPacket",
    "SignalType",
    "SourceRevision",
    "SubjectIdentity",
    "UnresolvedUnknown",
    "ValidationStatus",
    "WorkflowIdentity",
    "canonical_bytes",
    "decide",
    "load_and_validate_packet",
    "max_raw_score",
    "packet_id",
    "promotion_score_hundredths",
    "signal_id",
    "validate_packet",
    "validate_packet_semantics",
    "write_packet_atomic",
]
```


### `l9ci/signals/model.py`

```python
"""Immutable signal packet models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "l9.signal-packet/v1"
SCHEMA_VERSION = "1.0.0"

AUTHORIZED_PRODUCERS = (
    "Quantum-L9/l9-ci-core",
    "Quantum-L9/l9-ci-sdk",
    "Quantum-L9/l9-ci-debt-resolver",
    "Quantum-L9/l9-ci-debt-intelligence",
    "Quantum-L9/l9-ci-debt-lsp",
    "Quantum-L9/l9-assurance",
    "Quantum-L9/l9-harness",
    "Quantum-L9/PR_Repair",
)

MAX_LOOP_GENERATION = 8


class SignalType(str, Enum):
    ARCHITECTURE_BOUNDARY = "architecture_boundary_signal"
    CAPABILITY = "capability_signal"
    CONFIGURATION = "configuration_signal"
    DEPENDENCY = "dependency_signal"
    FINDING = "finding_signal"
    FAILURE_FINGERPRINT = "failure_fingerprint_signal"
    VALIDATION = "validation_signal"
    ASSURANCE = "assurance_signal"
    POLICY = "policy_signal"
    REPAIR = "repair_signal"
    ROLLBACK = "rollback_signal"
    REGRESSION = "regression_signal"
    RECURRENCE = "recurrence_signal"
    EFFECTIVENESS = "effectiveness_signal"
    DRIFT = "drift_signal"
    OPERATOR_CORRECTION = "operator_correction_signal"
    FRICTION = "friction_signal"
    LOAD = "load_signal"
    ARTIFACT_LINEAGE = "artifact_lineage_signal"
    COMPATIBILITY = "compatibility_signal"
    MESH_EDGE = "mesh_edge_signal"
    UNKNOWN = "unknown_signal"
    NEXT_ACTION = "next_action_signal"


class PromotionDecision(str, Enum):
    PROMOTE = "promote"
    DEFER = "defer"
    EVIDENCE_ONLY = "evidence_only"
    REJECT = "reject"


class ValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    INCOMPLETE = "incomplete"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    kind: str
    reference: str
    digest: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "reference": self.reference, "digest": self.digest}


@dataclass(frozen=True, slots=True)
class Recurrence:
    fingerprint: str
    observed_count: int
    distinct_scope_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "fingerprint": self.fingerprint,
            "observed_count": self.observed_count,
        }
        if self.distinct_scope_count is not None:
            payload["distinct_scope_count"] = self.distinct_scope_count
        return payload


@dataclass(frozen=True, slots=True)
class SignalDimensions:
    autonomy_gain: int = 0
    future_reuse: int = 0
    recurrence_prevention: int = 0
    compounding_leverage: int = 0
    proof_gain: int = 0
    boundary_clarity: int = 0
    friction_reduction: int = 0
    load_reduction: int = 0
    reversibility: int = 0
    evidence_confidence: int = 0
    complexity_cost: int = 0
    runtime_coupling: int = 0
    blast_radius_increase: int = 0
    authority_ambiguity: int = 0
    noise_risk: int = 0

    def __post_init__(self) -> None:
        for name in self.__slots__:
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"dimension {name} must be an integer")
            if not 0 <= value <= 5:
                raise ValueError(f"dimension {name} must be within 0..5")

    def to_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in sorted(self.__slots__)}


@dataclass(frozen=True, slots=True)
class Signal:
    signal_id: str
    signal_type: SignalType
    source_evidence: tuple[EvidenceReference, ...]
    confidence: Confidence
    recurrence: Recurrence
    dimensions: SignalDimensions
    promotion_score_hundredths: int
    promotion_decision: PromotionDecision
    expected_behavior_change: str
    owner: str
    target_loop: str | None = None
    next_action: str | None = None
    downstream_reach: int | None = None
    prohibited_risk: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_evidence:
            raise ValueError("signal requires at least one evidence reference")
        if self.promotion_decision is PromotionDecision.PROMOTE:
            if not self.target_loop:
                raise ValueError("promoted signal requires target_loop")
            if not self.next_action:
                raise ValueError("promoted signal requires next_action")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type.value,
            "source_evidence": [item.to_dict() for item in self.source_evidence],
            "confidence": self.confidence.value,
            "recurrence": self.recurrence.to_dict(),
            "dimensions": self.dimensions.to_dict(),
            "promotion_score_hundredths": self.promotion_score_hundredths,
            "promotion_decision": self.promotion_decision.value,
            "target_loop": self.target_loop,
            "expected_behavior_change": self.expected_behavior_change,
            "owner": self.owner,
            "next_action": self.next_action,
            "limitations": sorted(set(self.limitations)),
        }
        if self.downstream_reach is not None:
            payload["downstream_reach"] = self.downstream_reach
        if self.prohibited_risk:
            payload["prohibited_risk"] = sorted(set(self.prohibited_risk))
        return payload


@dataclass(frozen=True, slots=True)
class SourceRevision:
    commit: str | None
    dirty: bool

    def to_dict(self) -> dict[str, Any]:
        return {"commit": self.commit, "dirty": self.dirty}


@dataclass(frozen=True, slots=True)
class SubjectIdentity:
    kind: str
    value: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}


@dataclass(frozen=True, slots=True)
class ProducerIdentity:
    id: str
    version: str
    build_digest: str | None = None

    def __post_init__(self) -> None:
        if self.id not in AUTHORIZED_PRODUCERS:
            raise ValueError(f"unauthorized producer identity: {self.id}")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"id": self.id, "version": self.version}
        if self.build_digest is not None:
            payload["build_digest"] = self.build_digest
        return payload


@dataclass(frozen=True, slots=True)
class WorkflowIdentity:
    workflow: str
    profile: str
    attempt: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"workflow": self.workflow, "profile": self.profile}
        if self.attempt is not None:
            payload["attempt"] = self.attempt
        return payload


@dataclass(frozen=True, slots=True)
class RoutedLoop:
    loop_id: str
    generation: int
    idempotency_key: str

    def __post_init__(self) -> None:
        if not 0 <= self.generation <= MAX_LOOP_GENERATION:
            raise ValueError("loop generation exceeds bounded propagation depth")

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "generation": self.generation,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True, slots=True)
class RejectedNoise:
    signal_id: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"signal_id": self.signal_id, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class UnresolvedUnknown:
    unknown_id: str
    category: str
    description: str
    impact: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "unknown_id": self.unknown_id,
            "category": self.category,
            "description": self.description,
            "impact": self.impact,
        }


@dataclass(frozen=True, slots=True)
class NextAction:
    action: str
    owner: str
    blocking: bool

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "owner": self.owner, "blocking": self.blocking}


@dataclass(frozen=True, slots=True)
class ArtifactLineageEntry:
    artifact: str
    digest: str
    role: str

    def to_dict(self) -> dict[str, Any]:
        return {"artifact": self.artifact, "digest": self.digest, "role": self.role}


@dataclass(frozen=True, slots=True)
class SignalPacket:
    sdk_version: str
    packet_id: str
    root_execution_id: str
    source_execution_id: str
    parent_execution_id: str | None
    source_repository: str
    source_revision: SourceRevision
    subject_identity: SubjectIdentity
    producer_identity: ProducerIdentity
    workflow_identity: WorkflowIdentity
    configuration_digest: str
    dependency_manifest_digest: str
    input_artifact_digests: dict[str, str]
    extracted_signals: tuple[Signal, ...]
    rejected_noise: tuple[RejectedNoise, ...]
    routed_loops: tuple[RoutedLoop, ...]
    unresolved_unknowns: tuple[UnresolvedUnknown, ...]
    next_actions: tuple[NextAction, ...]
    artifact_lineage: tuple[ArtifactLineageEntry, ...]
    validation_status: ValidationStatus
    limitations: tuple[str, ...] = field(default=())

    def to_dict(self) -> dict[str, Any]:
        return {
            "$schema_id": SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "sdk_version": self.sdk_version,
            "packet_id": self.packet_id,
            "root_execution_id": self.root_execution_id,
            "source_execution_id": self.source_execution_id,
            "parent_execution_id": self.parent_execution_id,
            "source_repository": self.source_repository,
            "source_revision": self.source_revision.to_dict(),
            "subject_identity": self.subject_identity.to_dict(),
            "producer_identity": self.producer_identity.to_dict(),
            "workflow_identity": self.workflow_identity.to_dict(),
            "configuration_digest": self.configuration_digest,
            "dependency_manifest_digest": self.dependency_manifest_digest,
            "input_artifact_digests": dict(sorted(self.input_artifact_digests.items())),
            "extracted_signals": [
                signal.to_dict()
                for signal in sorted(self.extracted_signals, key=lambda item: item.signal_id)
            ],
            "promotion_decisions": [
                {
                    "signal_id": signal.signal_id,
                    "decision": signal.promotion_decision.value,
                    "reasons": [signal.expected_behavior_change],
                }
                for signal in sorted(self.extracted_signals, key=lambda item: item.signal_id)
            ],
            "rejected_noise": [
                item.to_dict()
                for item in sorted(self.rejected_noise, key=lambda entry: entry.signal_id)
            ],
            "routed_loops": [
                item.to_dict()
                for item in sorted(
                    self.routed_loops, key=lambda entry: (entry.loop_id, entry.generation)
                )
            ],
            "unresolved_unknowns": [
                item.to_dict()
                for item in sorted(self.unresolved_unknowns, key=lambda entry: entry.unknown_id)
            ],
            "next_actions": [
                item.to_dict()
                for item in sorted(self.next_actions, key=lambda entry: entry.action)
            ],
            "artifact_lineage": [
                item.to_dict()
                for item in sorted(
                    self.artifact_lineage, key=lambda entry: (entry.role, entry.artifact)
                )
            ],
            "validation_status": self.validation_status.value,
            "limitations": sorted(set(self.limitations)),
        }
```


### `l9ci/signals/scoring.py`

```python
"""Deterministic integer promotion scoring.

Floating point is deliberately absent. Every score is computed with integer
arithmetic so that two runs on different machines produce byte-identical
canonical output.
"""

from __future__ import annotations

from .model import PromotionDecision, SignalDimensions

POSITIVE_WEIGHTS: dict[str, int] = {
    "autonomy_gain": 5,
    "future_reuse": 5,
    "recurrence_prevention": 5,
    "compounding_leverage": 5,
    "proof_gain": 4,
    "boundary_clarity": 4,
    "friction_reduction": 4,
    "load_reduction": 3,
    "reversibility": 3,
    "evidence_confidence": 3,
}

NEGATIVE_WEIGHTS: dict[str, int] = {
    "complexity_cost": -4,
    "runtime_coupling": -4,
    "blast_radius_increase": -5,
    "authority_ambiguity": -5,
    "noise_risk": -5,
}

PROHIBITED_RISKS: frozenset[str] = frozenset(
    {
        "authority_ambiguity",
        "blast_radius_unbounded",
        "irreversible_mutation",
        "unverified_evidence",
        "protected_path_touch",
    }
)

PROMOTE_THRESHOLD_HUNDREDTHS = 7500
DEFER_THRESHOLD_HUNDREDTHS = 5000
EVIDENCE_ONLY_THRESHOLD_HUNDREDTHS = 4000

MAX_DIMENSION_VALUE = 5


def max_raw_score() -> int:
    """Maximum achievable raw score with zero negative dimensions."""
    return sum(POSITIVE_WEIGHTS.values()) * MAX_DIMENSION_VALUE


def raw_score(dimensions: SignalDimensions) -> int:
    total = 0
    for name, weight in POSITIVE_WEIGHTS.items():
        total += weight * getattr(dimensions, name)
    for name, weight in NEGATIVE_WEIGHTS.items():
        total += weight * getattr(dimensions, name)
    return total


def promotion_score_hundredths(dimensions: SignalDimensions) -> int:
    """Normalize the raw score to 0..10000 using floor division only."""
    raw = raw_score(dimensions)
    if raw <= 0:
        return 0
    scaled = (raw * 10000) // max_raw_score()
    return min(scaled, 10000)


def decide(
    dimensions: SignalDimensions,
    *,
    prohibited_risk: tuple[str, ...] = (),
    has_blocking_unknown: bool = False,
    missing_evidence: bool = False,
    behavior_change_proven: bool = True,
) -> tuple[int, PromotionDecision, tuple[str, ...]]:
    """Return the score, decision, and ordered machine-readable reasons."""
    score = promotion_score_hundredths(dimensions)
    reasons: list[str] = []

    unknown_risks = sorted(set(prohibited_risk) - PROHIBITED_RISKS)
    if unknown_risks:
        raise ValueError(f"unrecognized prohibited risk: {unknown_risks}")

    if prohibited_risk:
        reasons.append("prohibited_risk_present")
        return score, PromotionDecision.REJECT, tuple(reasons)

    if score < EVIDENCE_ONLY_THRESHOLD_HUNDREDTHS:
        reasons.append("score_below_evidence_threshold")
        return score, PromotionDecision.REJECT, tuple(reasons)

    if score >= PROMOTE_THRESHOLD_HUNDREDTHS and not has_blocking_unknown:
        reasons.append("score_meets_promote_threshold")
        return score, PromotionDecision.PROMOTE, tuple(reasons)

    if has_blocking_unknown:
        reasons.append("blocking_unknown_present")

    if score >= DEFER_THRESHOLD_HUNDREDTHS and missing_evidence:
        reasons.append("missing_evidence")
        return score, PromotionDecision.DEFER, tuple(reasons)

    if score >= DEFER_THRESHOLD_HUNDREDTHS and has_blocking_unknown:
        return score, PromotionDecision.DEFER, tuple(reasons)

    if not behavior_change_proven:
        reasons.append("behavior_change_unproven")
        return score, PromotionDecision.EVIDENCE_ONLY, tuple(reasons)

    reasons.append("score_below_promote_threshold")
    return score, PromotionDecision.EVIDENCE_ONLY, tuple(reasons)
```


### `l9ci/signals/serialize.py`

```python
"""Deterministic serialization, identity derivation, and atomic writes."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

_JSON_SEPARATORS = (",", ":")


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Canonical JSON: sorted keys, compact separators, UTF-8, no trailing newline."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=_JSON_SEPARATORS,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def signal_id(payload: dict[str, Any]) -> str:
    """Derive a signal identity from its identity-bearing fields only.

    Volatile fields (scores, decisions, next actions) are excluded so that the
    same underlying observation keeps a stable identity across re-scoring.
    """
    identity = {
        "signal_type": payload["signal_type"],
        "source_evidence": payload["source_evidence"],
        "recurrence_fingerprint": payload["recurrence"]["fingerprint"],
        "owner": payload["owner"],
    }
    return f"sig:{_digest(identity)}"


def packet_id(payload: dict[str, Any]) -> str:
    """Derive packet identity, excluding the identity field itself."""
    identity = {
        key: value
        for key, value in payload.items()
        if key not in {"packet_id", "limitations"}
    }
    return f"pkt:{_digest(identity)}"


def write_packet_atomic(payload: dict[str, Any], destination: Path) -> Path:
    """Write canonical bytes atomically. Never leaves a partial artifact."""
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(payload)
    handle, temporary_name = tempfile.mkstemp(
        dir=str(destination.parent), prefix=".signal-packet-", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, destination)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return destination
```


### `l9ci/signals/validate.py`

```python
"""Schema and semantic validation for signal packets."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .serialize import canonical_bytes, packet_id, signal_id

SCHEMA_ROOT = Path(__file__).resolve().parents[^1] / "schemas" / "v1"
PACKET_SCHEMA_NAME = "signal-packet.schema.json"
SIGNAL_SCHEMA_NAME = "signal.schema.json"

_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|password|token|private[_-]?key|BEGIN [A-Z ]*PRIVATE KEY)"
)


class SignalContractError(ValueError):
    """Raised when a signal packet violates its contract."""


def _load_registry() -> Registry:
    registry = Registry()
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
        registry = registry.with_resource(
            uri=path.name, resource=Resource.from_contents(document)
        )
    return registry


def _packet_validator() -> Draft202012Validator:
    with (SCHEMA_ROOT / PACKET_SCHEMA_NAME).open(encoding="utf-8") as handle:
        schema = json.load(handle)
    return Draft202012Validator(schema, registry=_load_registry())


def validate_packet(payload: dict[str, Any]) -> None:
    """Schema validation. Raises SignalContractError with every error listed."""
    errors = sorted(
        _packet_validator().iter_errors(payload), key=lambda error: list(error.path)
    )
    if errors:
        rendered = "; ".join(
            f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise SignalContractError(f"signal packet schema validation failed: {rendered}")


def validate_packet_semantics(payload: dict[str, Any]) -> None:
    """Semantic validation. Schema validation alone is never sufficient."""
    problems: list[str] = []

    expected_packet = packet_id(payload)
    if payload["packet_id"] != expected_packet:
        problems.append(
            f"packet_id mismatch: declared {payload['packet_id']} "
            f"derived {expected_packet}"
        )

    declared_ids = [signal["signal_id"] for signal in payload["extracted_signals"]]
    if len(declared_ids) != len(set(declared_ids)):
        problems.append("duplicate signal_id within packet")

    for signal in payload["extracted_signals"]:
        derived = signal_id(signal)
        if signal["signal_id"] != derived:
            problems.append(
                f"signal_id mismatch: declared {signal['signal_id']} derived {derived}"
            )
        if signal["promotion_decision"] == "promote":
            if not signal.get("target_loop"):
                problems.append(f"{signal['signal_id']}: promoted without target_loop")
            if not signal.get("next_action"):
                problems.append(f"{signal['signal_id']}: promoted without next_action")

    decision_ids = {entry["signal_id"] for entry in payload["promotion_decisions"]}
    if decision_ids != set(declared_ids):
        problems.append("promotion_decisions do not cover every extracted signal")

    noise_ids = {entry["signal_id"] for entry in payload["rejected_noise"]}
    if noise_ids & set(declared_ids):
        problems.append("signal appears in both extracted_signals and rejected_noise")

    seen_loops: set[tuple[str, str]] = set()
    for loop in payload["routed_loops"]:
        key = (loop["loop_id"], loop["idempotency_key"])
        if key in seen_loops:
            problems.append(f"duplicate idempotency key for loop {loop['loop_id']}")
        seen_loops.add(key)

    blocking_unknown = any(
        unknown["impact"] == "decision" for unknown in payload["unresolved_unknowns"]
    )
    if blocking_unknown and payload["validation_status"] == "valid":
        problems.append("decision-impacting unknown cannot yield validation_status valid")

    match = _SECRET_PATTERN.search(canonical_bytes(payload).decode("utf-8"))
    if match is not None:
        problems.append(f"secret-like token present in packet: {match.group(0)!r}")

    if problems:
        raise SignalContractError("; ".join(problems))


def load_and_validate_packet(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SignalContractError("signal packet must be a JSON object")
    validate_packet(payload)
    validate_packet_semantics(payload)
    return payload
```

`jsonschema` and `referencing` are already declared runtime dependencies, so `requirements.txt` is unchanged — which matters, because the SDK is executed from source over `PYTHONPATH` by Core's `provision-sdk` action and any new runtime import would require touching that file.[^1]

### `tests/signals/test_scoring.py`

```python
from l9ci.signals import decide, max_raw_score, promotion_score_hundredths
from l9ci.signals.model import PromotionDecision, SignalDimensions


def _maximal() -> SignalDimensions:
    return SignalDimensions(
        autonomy_gain=5,
        future_reuse=5,
        recurrence_prevention=5,
        compounding_leverage=5,
        proof_gain=5,
        boundary_clarity=5,
        friction_reduction=5,
        load_reduction=5,
        reversibility=5,
        evidence_confidence=5,
    )


def test_max_raw_score_matches_declared_weights() -> None:
    assert max_raw_score() == 205


def test_maximal_dimensions_saturate_score() -> None:
    assert promotion_score_hundredths(_maximal()) == 10000


def test_zero_dimensions_score_zero() -> None:
    assert promotion_score_hundredths(SignalDimensions()) == 0


def test_negative_dimensions_cannot_produce_negative_score() -> None:
    dimensions = SignalDimensions(noise_risk=5, authority_ambiguity=5)
    assert promotion_score_hundredths(dimensions) == 0


def test_prohibited_risk_forces_reject_regardless_of_score() -> None:
    score, decision, reasons = decide(
        _maximal(), prohibited_risk=("irreversible_mutation",)
    )
    assert score == 10000
    assert decision is PromotionDecision.REJECT
    assert reasons == ("prohibited_risk_present",)


def test_blocking_unknown_downgrades_promote_to_defer() -> None:
    _, decision, reasons = decide(_maximal(), has_blocking_unknown=True)
    assert decision is PromotionDecision.DEFER
    assert "blocking_unknown_present" in reasons


def test_unproven_behavior_change_yields_evidence_only() -> None:
    dimensions = SignalDimensions(
        autonomy_gain=3,
        future_reuse=3,
        recurrence_prevention=2,
        compounding_leverage=2,
        proof_gain=2,
        boundary_clarity=2,
    )
    _, decision, reasons = decide(dimensions, behavior_change_proven=False)
    assert decision is PromotionDecision.EVIDENCE_ONLY
    assert "behavior_change_unproven" in reasons


def test_scoring_is_pure_integer_arithmetic() -> None:
    assert isinstance(promotion_score_hundredths(_maximal()), int)
```


### `tests/signals/test_determinism.py`

```python
import json

from l9ci.signals import canonical_bytes, packet_id, signal_id


def _signal() -> dict[str, object]:
    return {
        "signal_id": "",
        "signal_type": "failure_fingerprint_signal",
        "source_evidence": [
            {"kind": "workflow_run", "reference": "run/1", "digest": "0" * 64}
        ],
        "confidence": "high",
        "recurrence": {"fingerprint": "a" * 64, "observed_count": 3},
        "owner": "Quantum-L9/l9-ci-debt-resolver",
    }


def test_canonical_bytes_are_key_order_independent() -> None:
    left = {"b": 1, "a": {"d": 2, "c": 3}}
    right = {"a": {"c": 3, "d": 2}, "b": 1}
    assert canonical_bytes(left) == canonical_bytes(right)


def test_canonical_bytes_reject_non_finite_numbers() -> None:
    try:
        canonical_bytes({"value": float("nan")})
    except ValueError:
        return
    raise AssertionError("NaN must be rejected")


def test_signal_id_is_stable_across_score_changes() -> None:
    base = _signal()
    scored_low = dict(base, promotion_score_hundredths=1000)
    scored_high = dict(base, promotion_score_hundredths=9000)
    assert signal_id(scored_low) == signal_id(scored_high)


def test_signal_id_changes_with_evidence() -> None:
    base = _signal()
    mutated = dict(base)
    mutated["source_evidence"] = [
        {"kind": "workflow_run", "reference": "run/2", "digest": "1" * 64}
    ]
    assert signal_id(base) != signal_id(mutated)


def test_packet_id_excludes_itself_and_limitations() -> None:
    payload = {"packet_id": "pkt:" + "0" * 64, "limitations": ["x"], "value": 1}
    other = {"packet_id": "pkt:" + "f" * 64, "limitations": ["y"], "value": 1}
    assert packet_id(payload) == packet_id(other)


def test_canonical_bytes_round_trip() -> None:
    payload = {"alpha": [1, 2, 3], "beta": {"gamma": "\u00e9"}}
    assert json.loads(canonical_bytes(payload).decode("utf-8")) == payload
```


### `.l9/architecture.yaml` — layer addition

```yaml
  signals:
    package: l9ci.signals
    responsibility:
      - canonical signal packet contract
      - deterministic promotion scoring
      - signal identity derivation
      - signal packet validation
    may_depend_on:
      - contracts
    must_not_depend_on:
      - providers
      - policy
      - gates
      - pipeline
      - integration
      - repository
      - capabilities
      - execution
      - artifacts
```

Add to `forbidden_dependency_edges`: `signals_to_providers`, `signals_to_policy`, `signals_to_gates`, `signals_to_pipeline`, `signals_to_integration`, `signals_to_artifacts`, `contracts_to_signals`, `providers_to_signals`, `artifacts_to_signals`. Add `l9ci.signals` to `public_surface.packages`.[^1]

The `signals → artifacts` edge is deliberately forbidden. Reusing the bundle serializer would couple signal emission to the analysis artifact stack, and `serialize.py` above is ~40 lines of stdlib. Duplicating a canonical-JSON convention is cheaper than coupling two contract families.

## Migration sequence

1. **P-105a** — land schemas, package, tests, `.l9` updates, version bump to 1.1.0 in both `l9ci/__init__.py` and `.l9/integration-contract.yaml` (they are asserted equal). Zero producers wired. Zero pin changes.[^1]
2. **P-103** — immutable checkout on the three Intelligence publication workflows; run in parallel, different repo.[^4]
3. **P-501 (new, blocking)** — reconcile Assurance's producer registry with SDK reality: resolve `UNKNOWN-001`, decide whether `candidateVersionRange >=2.0.0 <3.0.0` or the SDK's `1.x` line is authoritative, and either implement the six registered checks in the SDK CLI or mark them `Unknown` and remove from the `pull-request` profile.[^2][^1]
4. **P-502 (new)** — specify the `l9.finding-bundle/v1 → l9.observation/v1` adapter and assign its owner. Core is the wrong owner (it would gain finding semantics); SDK is the right one, as a projection peer to `agent_payload`.[^1]
5. **P-104** — "Core publishes, Assurance decides" ADR.
6. **P-101 / P-102 / P-202 / P-203 / P-204** — unchanged from the prior plan.
7. **Loops 1–3**, then Loop 4 once P-501 and P-502 clear.

## Validation commands

```bash
# Schema well-formedness and inventory
python -m pytest tests/architecture -q

# Signals package
python -m pytest tests/signals -q

# Boundary enforcement (must show zero violations)
python -m pytest tests/architecture/test_dependency_boundaries.py -q

# Version coherence: these two must match
python -c "import l9ci; print(l9ci.__version__)"
grep -A2 '^metadata:' .l9/integration-contract.yaml | grep version

# No new runtime dependency introduced
git diff --exit-code requirements.txt

# Pin invariance across the constellation
grep -rhoE '[0-9a-f]{40}' .github/workflows | sort -u
```

Expected: `f88116503430aa18992b70d8d31063e34ff97ef1` unchanged, `requirements.txt` diff empty, all suites green. **I cannot execute these** — no repository mutation or execution authority is granted, and the ROADMAP explicitly restricts this work to architecture, contracts, schemas, file plans, and validation specifications. Every file above is paste-ready and unexecuted.[^5]

## Scorecard

| Dimension | Before | After P-105a |
| :-- | :-- | :-- |
| Canonical signal packet | none located [^5] | 1 schema, 23 signal types, 15 scored dimensions |
| Scoring determinism | undefined | integer-only, floor division, no float |
| Signal identity stability | undefined | score-independent, evidence-derived |
| Loops unblocked | 0 of 4 | 3 of 4 (Loop 4 held by F-11/F-12/F-13) |
| New runtime dependencies | — | 0 |
| Cross-repo pin changes | — | 0 |
| SDK forbidden edges violated | 0 [^1] | 0 |
| Assurance verdict producers | 2 [^2][^3] | 2 until P-104 |

## Blockers

- **F-13** is the hard one. Assurance's only registered producer is `pending`, with a version range that does not intersect the SDK's declared contract version. Until reconciled, every Assurance decision is correctly `indeterminate` and Loop 4 is unschedulable.[^2][^1]
- **U-6** — l9-harness remains uninspected in this thread.
- **U-8** — SAFIR and Trace are named in the ROADMAP but present in no inspected repository; they stay `Unknown` and receive no invented semantics.[^5]

For P-501, is the SDK expected to grow the six registered check commands (`l9.lint`, `l9.tests`, `l9.sdk-validation`, and the rest), or should Assurance's check registry be narrowed to what the SDK actually implements today?

<div align="center">⁂</div>

[^1]: quantum-l9-l9-ci-sdk-8a5edab282632443.txt

[^2]: quantum-l9-l9-assurance-8a5edab282632443-1.txt

[^3]: quantum-l9-l9-ci-core-8a5edab282632443-1.txt

[^4]: quantum-l9-l9-ci-debt-intelligence-8a5edab282632443.txt

[^5]: ROADMAP-Target-CI-Constellation-Architecture.docx

