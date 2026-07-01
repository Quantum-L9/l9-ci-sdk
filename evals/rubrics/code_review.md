<!-- L9_META
l9_schema: 1
origin: l9-ci-sdk
layer: [evals, rubric]
tags: [L9_CI, agent-review-loop, rubric]
owner: platform
status: active
/L9_META -->

# Code Review Eval Rubric

Scores the L9 review agents against golden PR diffs (L9 Platform Doctrine eval taxonomy).

| Dimension | Measure | Threshold |
|---|---|---|
| structured_output_validity | report has required keys; findings serialize | **hard-fail** if invalid |
| regression | expected finding categories present; count ≥ min_findings | **hard-fail** if a golden case regresses |
| factuality | flagged findings correspond to real violations in the golden file | manual review of new cases |
| cost | tokens + USD per run (LLM agent only) | soft-fail on spike |

Golden sets are production-like, PII-removed, version-controlled, and never deleted.
