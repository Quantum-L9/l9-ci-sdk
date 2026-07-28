"""SDK-owned, versioned rulesets shipped as package data.

Sub-packages under ``l9_ci.rulesets`` bundle provider-specific rule files and
identity maps that every downstream consumer inherits by default, so a
per-repository consumer needs zero local rule authoring. See
``l9_ci.rulesets.semgrep`` for the Semgrep Python/TypeScript baseline
ruleset and packaged identity map.
"""

from __future__ import annotations

__all__: list[str] = []
