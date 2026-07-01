from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_CI_WORKFLOW = '''name: PR Pipeline Gate

on:
  pull_request:
  push:
    branches: [main]

jobs:
  pr_pipeline:
    uses: Quantum-L9/l9-ci-core/.github/workflows/pr-pipeline.yml@v1
    with:
      python-version: "3.12"
      source-dir: "."
      test-dir: "tests"
'''

DEFAULT_REQUIREMENTS_CI = '''ruff>=0.15.0,<1.0.0
mypy>=1.14.0,<3.0.0
pytest>=8.3.0
pytest-cov>=6.0.0
pytest-xdist>=3.8.0
pytest-timeout>=2.4.0
bandit>=1.9.0
pip-audit>=2.9.0
safety>=3.0.0
pip-licenses>=4.0.0
'''

DEFAULT_GITLEAKS = '''title = "L9 Universal Repo Gitleaks Configuration"

[[rules]]
id = "generic-api-key"
description = "Generic API Key"
regex = ''' + "'''(?i)(api[_-]?key|apikey|api[_-]?secret)\\s*[=:]\\s*['\"][a-zA-Z0-9_\\-]{20,}['\"]'''" + '''
tags = ["api", "generic"]

[allowlist]
description = "Template and test allowlist"
paths = [''' + "'''tests/''', '''docs/''', '''.env.example''', '''.env.template''']" + '''
regexTarget = "match"
regexes = [''' + "'''(?i)example|placeholder|dummy|test|fake|mock|sample''']" + '''
'''

DEFAULT_PRE_COMMIT = '''repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: [--maxkb=1000]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.8
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: local
    hooks:
      - id: l9-transport-packet
        name: L9 TransportPacket contract prohibition
        entry: l9-ci check-transport-packet . --exclude tests
        language: system
        pass_filenames: false
      - id: l9-deprecated-api
        name: L9 deprecated API check
        entry: l9-ci check-deprecated-api . --exclude tests
        language: system
        pass_filenames: false
'''

DEFAULT_PYPROJECT = '''[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "A", "C4", "TCH"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
'''

DEFAULT_QUALITY_THRESHOLDS = '''# --- L9_META ---
# l9_schema: 1
# origin: l9-repo-template
# layer: [ci, governance, thresholds]
# tags: [L9_TEMPLATE, thresholds, fail-closed]
# owner: platform
# status: active
# --- /L9_META ---
version: 1
coverage:
  default: 80
  l9_ci_sdk: 85
  l9_ci_core: 80
  minimum_floor: 80
  allow_repo_override: true
  override_requires:
    - l9-validated:approve
    - platform_owner_review
security:
  max_critical_findings: 0
  max_high_findings: 0
rule_modes:
  transport_packet_contract: blocking
  direct_node_dispatch: advisory
  handler_signature: advisory
  pii_logging: advisory
'''

DEFAULT_AUDIT_BASELINE = '''{
  "version": 1,
  "baseline_name": "l9-ci-governance-baseline",
  "semantics": {
    "in_baseline_and_not_touched": "advisory",
    "in_baseline_and_touched_dangerous": "blocking",
    "not_in_baseline_and_high_or_critical": "blocking",
    "not_in_baseline_and_low_medium": "advisory"
  },
  "entries": []
}
'''

DEFAULT_AUDIT_POLICY = '''# --- L9_META ---
# l9_schema: 1
# origin: l9-repo-template
# layer: [ci, governance, policy]
# tags: [L9_TEMPLATE, audit-policy, fail-closed]
# owner: platform
# status: active
# --- /L9_META ---
version: 1
policy_name: l9-ci-governance-policy
scope: repository_ci_governance
canonical_pr_classes:
  - docs_only
  - ci_workflow
  - dependency_python
  - app_code
  - security
  - compliance
  - unknown_diff
baseline:
  source: .github/governance/audit-baseline.json
  malformed_baseline: fail_closed
  missing_baseline: fail_closed
thresholds:
  source: .github/governance/quality-thresholds.yaml
  malformed_thresholds: fail_closed
  missing_thresholds: fail_closed
trio_wiring:
  validator_approval_required_label: l9-validated:approve
required_contract_controls:
  transport_packet_contract: fail_closed
'''

DEFAULT_CI_ROUTING_POLICY = '''# --- L9_META ---
# l9_schema: 1
# origin: l9-repo-template
# layer: [ci, governance, routing]
# tags: [L9_TEMPLATE, routing, policy]
# owner: platform
# status: active
# --- /L9_META ---
version: 1
routing_policy:
  docs_only:
    blocking: [markdown_lint]
  ci_workflow:
    blocking: [workflow_yaml_parse, classifier_integrity]
  dependency_python:
    blocking: [dependency_install, lockfile_consistency]
  app_code:
    blocking: [lint, type_check, tests]
  security:
    blocking: [secrets_scan, semgrep, fail_closed_high_critical]
  compliance:
    blocking: [contract_control, architecture_compliance]
  unknown_diff:
    blocking: [validate, lint, tests, semgrep, secrets_scan, contract_control]
    behavior: fail_closed
'''

DEFAULT_LABEL_TAXONOMY = '''# --- L9_META ---
# l9_schema: 1
# origin: l9-repo-template
# layer: [ci, governance, labels]
# tags: [L9_TEMPLATE, labels, taxonomy]
# owner: platform
# status: active
# --- /L9_META ---
version: 1
labels:
  type:
    - type:ci
    - type:security
    - type:docs
    - type:deps
  area:
    - area:workflows
    - area:transport
    - area:runtime
  risk:
    - risk:blocking
    - risk:advisory
'''

DEFAULT_SHARED_SPEC = '''# --- L9_META ---
# l9_schema: 1
# origin: l9-repo-template
# layer: [ci, governance, classifier]
# tags: [L9_TEMPLATE, classifier, routing, policy]
# owner: platform
# status: active
# --- /L9_META ---
version: 1
name: l9-ci-shared-spec
classifier:
  canonical_classes: [docs_only, ci_workflow, dependency_python, app_code, security, compliance, unknown_diff]
  unknown_class: unknown_diff
  docs_only_class: docs_only
  priority: [security, compliance, ci_workflow, dependency_python, app_code, docs_only]
  taxonomy:
    docs:
      class: docs_only
      suffixes: [.md, .rst, .txt]
      prefixes: [docs/]
    ci_workflow:
      class: ci_workflow
      prefixes: [.github/workflows/, .github/scripts/]
    governance:
      class: compliance
      prefixes: [.github/governance/]
    dependencies:
      class: dependency_python
      exact: [requirements-ci.txt, pyproject.toml, uv.lock]
    security:
      class: security
      exact: [.gitleaks.toml, SECURITY.md]
    app_code:
      class: app_code
      suffixes: [.py, .pyi, .js, .ts, .go, .rs]
'''

DEFAULT_RULE_MODES = '''# --- L9_META ---
# l9_schema: 1
# origin: l9-repo-template
# layer: [ci, governance, rule-modes]
# tags: [L9_TEMPLATE, shadow-mode, advisory, blocking]
# owner: platform
# status: active
# --- /L9_META ---
version: 1
default_mode: blocking
rules:
  TRANSPORT-PACKET-CONTRACT: blocking
  DEPRECATED-API: advisory
  THRESHOLD-POLICY: blocking
  GOVERNANCE-APPROVAL: blocking
  PY-SYNTAX: blocking
  DIRECT-NODE-DISPATCH: advisory
  HANDLER-SIGNATURE: advisory
  PII-LOGGING: advisory
  OPTIONAL-STAGE-MISSING: advisory
  SEMGREP-EXPERIMENTAL: shadow
promotion:
  allowed_transitions:
    - shadow_to_advisory
    - advisory_to_blocking
  blocking_requires:
    - l9-validated:approve
    - platform_owner_review
  telemetry_artifact: artifacts/agent_review_payload.json
'''


@dataclass(frozen=True)
class BootstrapResult:
    root: Path
    created: list[Path]
    skipped: list[Path]


FILES: dict[str, str] = {
    ".github/workflows/ci.yml": DEFAULT_CI_WORKFLOW,
    ".github/governance/quality-thresholds.yaml": DEFAULT_QUALITY_THRESHOLDS,
    ".github/governance/audit-baseline.json": DEFAULT_AUDIT_BASELINE,
    ".github/governance/audit-policy.yml": DEFAULT_AUDIT_POLICY,
    ".github/governance/ci-routing-policy.yaml": DEFAULT_CI_ROUTING_POLICY,
    ".github/governance/label-taxonomy.yaml": DEFAULT_LABEL_TAXONOMY,
    ".github/governance/l9-ci-shared-spec.yaml": DEFAULT_SHARED_SPEC,
    ".github/governance/rule-modes.yaml": DEFAULT_RULE_MODES,
    "requirements-ci.txt": DEFAULT_REQUIREMENTS_CI,
    ".gitleaks.toml": DEFAULT_GITLEAKS,
    ".pre-commit-config.yaml": DEFAULT_PRE_COMMIT,
    "pyproject.toml": DEFAULT_PYPROJECT,
}


def init_repo(root: Path, *, force: bool = False) -> BootstrapResult:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    skipped: list[Path] = []
    for rel, content in FILES.items():
        path = root / rel
        if path.exists() and not force:
            skipped.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(path)
    return BootstrapResult(root=root, created=created, skipped=skipped)


def format_result(result: BootstrapResult) -> str:
    lines = [f"Initialized L9 repo CI at {result.root}"]
    if result.created:
        lines.append("created:")
        lines.extend(f"  {p.relative_to(result.root)}" for p in result.created)
    if result.skipped:
        lines.append("skipped existing files:")
        lines.extend(f"  {p.relative_to(result.root)}" for p in result.skipped)
    return "\n".join(lines)
