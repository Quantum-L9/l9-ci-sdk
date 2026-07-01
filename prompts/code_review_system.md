<!-- L9_META
l9_schema: 1
origin: l9-ci-sdk
layer: [prompts, llm-review]
tags: [L9_CI, agent-review-loop, prompt]
owner: platform
status: active
/L9_META -->

# code_review_system (llm_review_agent) — canonical prompt

Version: **v1** (see `prompt_versions.md`). The authoritative copy lives in
`l9_ci/review/llm_agent.py::SYSTEM_PROMPT`; this file documents and versions it.
Any change to the system prompt MUST bump the version and trigger `l9-ci review-eval`.

Focus: contract violations (TransportPacket only; Gate-only egress), security,
architecture/isolation, bugs, concurrency, error handling. Style/formatting/
docstrings are explicitly out of scope. Output is STRICT JSON.
