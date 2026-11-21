"""Withhold registry findings where the code declares a non-security use (ADR 0024).

The declarations come from ``l9_ci/rulesets/semgrep/rule-precision.yaml``; the
command layer passes them here as a plain mapping (registry rule ID ->
keyword), so this layer does not depend on the rulesets package.

A finding of a declared rule is withheld only when a call that starts on the
finding's line passes the declared keyword as the literal ``False``, read from
the file's Python syntax tree. Everything that cannot be shown keeps the
finding: an unreadable or unparseable file, a variable or expression instead of
the literal, or no matching call.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from pathlib import Path

from l9_ci.contracts import Finding

_MAX_BYTES = 2_000_000


def _syntax_tree(path: Path) -> ast.Module | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return None
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
        return None


def declares_keyword_false(tree: ast.Module, line: int, keyword: str) -> bool:
    """Whether a call starting on ``line`` passes ``keyword=False`` literally."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or node.lineno != line:
            continue
        for item in node.keywords:
            if (
                item.arg == keyword
                and isinstance(item.value, ast.Constant)
                and item.value.value is False
            ):
                return True
    return False


def withhold_declared_non_security(
    findings: Iterable[Finding],
    repository_root: Path,
    keywords: Mapping[str, str],
) -> tuple[tuple[Finding, ...], tuple[str, ...]]:
    """Withhold declared registry findings whose call passes ``keyword=False``.

    Returns the kept findings and one limitation per rule with every withheld
    site. The provider evidence is not touched, so it stays in the bundle.
    """
    root = repository_root.resolve()
    trees: dict[str, ast.Module | None] = {}
    kept: list[Finding] = []
    withheld: dict[tuple[str, str], list[str]] = {}
    for finding in findings:
        keyword = keywords.get(finding.provider_rule_id)
        location = finding.locations[0] if finding.locations else None
        if keyword is None or location is None or location.start_line is None:
            kept.append(finding)
            continue
        path = location.normalized_path
        if path not in trees:
            trees[path] = _syntax_tree(root / path)
        tree = trees[path]
        if tree is None or not declares_keyword_false(
            tree, location.start_line, keyword
        ):
            kept.append(finding)
            continue
        withheld.setdefault((finding.provider_rule_id, keyword), []).append(
            f"{path}:{location.start_line}"
        )
    limitations = tuple(
        f"registry rule {rule} not applicable where {keyword}=False declares a "
        f"non-security use: {len(sites)} finding(s) withheld, evidence kept "
        f"({', '.join(sorted(sites))})"
        for (rule, keyword), sites in sorted(withheld.items())
    )
    return tuple(kept), limitations


__all__ = ["declares_keyword_false", "withhold_declared_non_security"]
