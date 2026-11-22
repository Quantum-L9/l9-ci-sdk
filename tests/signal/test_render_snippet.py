"""Witnesses for l9_ci.signal (L9-SIGNAL-001, ADR 0025; CTO decision A).

The canonical finding bundle carries no source; Core renders the offending
lines through this SDK function from a checkout of the scanned revision.
Sensitive providers are masked without the file being read.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from l9_ci.contracts import Finding, SourceLocation
from l9_ci.gates import evaluate_gate
from l9_ci.signal import (
    MASK,
    render_findings,
    render_snippet,
    report_findings,
)

# Assembled at runtime so no secret-shaped literal sits in this file.
SECRET = "AKIA" + "Q" * 16


def _write(root: Path, relative: str, text: str | bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


def _lines(count: int) -> str:
    return "".join(f"line {number}\n" for number in range(1, count + 1))


def test_the_offending_line_has_two_lines_of_context_numbered_and_marked(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "src/a.py", _lines(10))
    snippet = render_snippet(tmp_path, "src/a.py", 5, sensitive=False)
    assert snippet.status == "rendered"
    assert [(item.number, item.offending) for item in snippet.lines] == [
        (3, False),
        (4, False),
        (5, True),
        (6, False),
        (7, False),
    ]
    assert snippet.render().splitlines() == [
        "  3 | line 3",
        "  4 | line 4",
        "> 5 | line 5",
        "  6 | line 6",
        "  7 | line 7",
    ]


def test_a_multi_line_finding_marks_every_line_and_clamps_at_file_edges(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "a.py", _lines(4))
    snippet = render_snippet(tmp_path, "a.py", 1, 2, sensitive=False)
    assert [(item.number, item.offending) for item in snippet.lines] == [
        (1, True),
        (2, True),
        (3, False),
        (4, False),
    ]
    tail = render_snippet(tmp_path, "a.py", 4, sensitive=False)
    assert [item.number for item in tail.lines] == [2, 3, 4]


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        (11, "line 11 is beyond the end of the file (10 lines)"),
        (0, "no line number"),
    ],
)
def test_an_out_of_range_line_is_unavailable_and_says_why(
    tmp_path: Path, line: int, reason: str
) -> None:
    _write(tmp_path, "a.py", _lines(10))
    snippet = render_snippet(tmp_path, "a.py", line, sensitive=False)
    assert (snippet.status, snippet.reason, snippet.lines) == (
        "unavailable",
        reason,
        (),
    )
    assert snippet.render() == f"a.py:{line}: {reason}"


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"\x89PNG\r\n\x1a\n\0\0\0", "binary file"),
        (b"caf\xe9\n", "not UTF-8 text"),
    ],
)
def test_binary_and_non_utf8_files_are_unavailable(
    tmp_path: Path, content: bytes, reason: str
) -> None:
    _write(tmp_path, "blob.bin", content)
    snippet = render_snippet(tmp_path, "blob.bin", 1, sensitive=False)
    assert (snippet.status, snippet.reason) == ("unavailable", reason)


def test_paths_outside_the_checkout_are_never_read(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = _write(tmp_path, "outside.py", SECRET + "\n")
    (root / "link.py").symlink_to(outside)
    for path, reason in (
        ("../outside.py", "not a repository path"),
        (str(outside), "not a repository path"),
        ("link.py", "not a regular file"),
        ("missing.py", "not a regular file"),
    ):
        snippet = render_snippet(root, path, 1, sensitive=False)
        assert (snippet.status, snippet.reason) == ("unavailable", reason), path
        assert SECRET not in json.dumps(snippet.to_dict())


def _finding(
    name: str, provider: str, path: str, line: int, message: str = "issue"
) -> Finding:
    return Finding(
        finding_id=f"fn-{name}",
        snapshot_id="snapshot-1",
        provider_id=provider,
        provider_rule_id=f"{provider}.rule",
        canonical_rule_id=f"L9-{name.upper()}",
        category="security",
        message=message,
        evidence_ids=(f"ev-{name}",),
        locations=(
            SourceLocation(normalized_path=path, start_line=line, end_line=line),
        ),
        fingerprint=f"{name:0<64}"[:64],
    )


@pytest.mark.parametrize("provider", ["gitleaks", "secret-scan", "trufflehog"])
def test_a_sensitive_provider_is_masked_and_no_secret_byte_leaves(
    tmp_path: Path, provider: str
) -> None:
    _write(tmp_path, "config/settings.py", f"KEY = '{SECRET}'\n")
    snippet = render_snippet(tmp_path, "config/settings.py", 1, sensitive=True)
    assert (snippet.status, snippet.reason, snippet.lines) == ("masked", MASK, ())
    finding = _finding("leak", provider, "config/settings.py", 1, f"found {SECRET}")
    reports, omitted = report_findings(tmp_path, [finding])
    (report,) = reports
    assert report.message == MASK and omitted == 0
    text = render_findings(tmp_path, [finding])
    payload = json.dumps([item.to_dict() for item in reports])
    assert text == f"L9-LEAK config/settings.py:1\nconfig/settings.py:1: {MASK}"
    for output in (text, payload):
        assert SECRET not in output
        assert SECRET[4:] not in output


def test_a_sensitive_finding_does_not_reach_the_gate_reasons(tmp_path: Path) -> None:
    """The gate names the rule and path:line, never the provider's message."""
    from l9_ci.contracts import (
        Coverage,
        CoverageStatus,
        FindingBundle,
        FindingClassification,
        ProviderRun,
        ResolutionStatus,
        RuleMode,
        SnapshotDescriptor,
    )

    finding = _finding("leak", "gitleaks", "config/settings.py", 1, f"found {SECRET}")
    bundle = FindingBundle(
        SDK_version="2.0.0",
        generated_at="2026-11-21T00:00:00Z",
        snapshot=SnapshotDescriptor("snapshot-1", "."),
        providers=(ProviderRun("gitleaks", "1.0.0", "8.24.3", "import", True),),
        evidence=(),
        findings=(finding,),
        classifications=(
            FindingClassification(
                finding_id="fn-leak",
                mode=RuleMode.BLOCKING,
                resolution_status=ResolutionStatus.DEFAULTED,
                used_default=True,
            ),
        ),
        provider_failures=(),
        coverage=(Coverage("gitleaks", CoverageStatus.COMPLETE, 1, 1, ()),),
    )
    result = json.dumps(evaluate_gate(bundle).to_dict())
    assert "L9-LEAK at config/settings.py:1" in result
    assert SECRET not in result


def test_reports_are_capped_at_twenty_with_a_count(tmp_path: Path) -> None:
    _write(tmp_path, "src/a.py", _lines(30))
    findings = [
        _finding(f"r{index:02d}", "semgrep", "src/a.py", index + 1)
        for index in range(23)
    ]
    reports, omitted = report_findings(tmp_path, findings)
    assert len(reports) == 20 and omitted == 3
    assert [item.line for item in reports] == list(range(1, 21))
    text = render_findings(tmp_path, findings)
    assert text.endswith("+3 more")
    assert text.startswith("L9-R00 src/a.py:1\n> 1 | line 1")


def test_report_field_names_are_the_payload_contract(tmp_path: Path) -> None:
    """The field names Core's agent-review payload uses (agreed with L2)."""
    _write(tmp_path, "src/a.py", _lines(3))
    (report,), _ = report_findings(tmp_path, [_finding("x", "semgrep", "src/a.py", 2)])
    payload = report.to_dict()
    assert sorted(payload) == [
        "end_line",
        "line",
        "message",
        "path",
        "rule_id",
        "snippet",
    ]
    assert sorted(payload["snippet"]) == ["end_line", "line", "lines", "path", "status"]
    assert payload["snippet"]["lines"][1] == {
        "line": 2,
        "text": "line 2",
        "offending": True,
    }
