"""Source snippets for failure reports (L9-SIGNAL-001, ADR 0025).

The canonical finding bundle carries no source content: a finding names its
rule, path, line, end line and message only. A consumer that reports a finding
to a person or an agent (Core's agent-review payload, CI log and step summary)
calls :func:`render_snippet` against a checkout of the scanned revision to show
the offending lines with two lines of context, line-numbered, the offending
lines marked.

A finding of a sensitive provider (a secret scanner) is never read: its snippet
is a full mask, so no byte of a detected secret can leave through this path.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from l9_ci.contracts import SUBJECT_CAP, Finding

SNIPPET_CONTEXT = 2
MASK = "[masked: sensitive provider]"
# Providers whose findings point at a secret. Their snippet is never read.
SENSITIVE_PROVIDERS = frozenset(
    {"gitleaks", "trufflehog", "detect-secrets", "secret-scan", "secret_scan"}
)
_MAX_FILE_BYTES = 2_000_000
_MAX_LINE_CHARS = 400


@dataclass(frozen=True, slots=True)
class SnippetLine:
    number: int
    text: str
    offending: bool

    def to_dict(self) -> dict[str, Any]:
        return {"line": self.number, "text": self.text, "offending": self.offending}


@dataclass(frozen=True, slots=True)
class Snippet:
    """The lines around a finding, a full mask, or why none could be read.

    ``status`` is ``rendered``, ``masked`` or ``unavailable``; ``lines`` is
    empty unless rendered, and ``reason`` names why a snippet is masked or
    unavailable.
    """

    path: str
    line: int
    end_line: int
    status: str
    lines: tuple[SnippetLine, ...] = ()
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "line": self.line,
            "end_line": self.end_line,
            "status": self.status,
            "lines": [item.to_dict() for item in self.lines],
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload

    def render(self) -> str:
        """Line-numbered text; ``>`` marks the offending lines."""
        if self.status != "rendered":
            return f"{self.path}:{self.line}: {self.reason}"
        width = len(str(self.lines[-1].number))
        return "\n".join(
            f"{'>' if item.offending else ' '} {item.number:>{width}} | {item.text}"
            for item in self.lines
        )


def _relative(path: str) -> str | None:
    pure = PurePosixPath(path.replace("\\", "/"))
    if pure.is_absolute() or not path or ".." in pure.parts:
        return None
    return pure.as_posix()


def render_snippet(
    root: Path,
    path: str,
    line: int,
    end_line: int | None = None,
    *,
    sensitive: bool,
    context: int = SNIPPET_CONTEXT,
) -> Snippet:
    """The offending lines of ``path`` under ``root`` with ``context`` lines around.

    ``root`` is a checkout of the scanned revision. ``sensitive`` masks the
    snippet fully without reading the file. A path that is absolute, escapes
    ``root``, is a symlink, is not a regular file, is binary, too large or not
    UTF-8, or a line outside the file, yields an ``unavailable`` snippet that
    says why.
    """
    end = end_line if end_line is not None and end_line >= line else line
    relative = _relative(path)
    shown_path = relative or "<invalid path>"
    if sensitive:
        return Snippet(shown_path, line, end, "masked", reason=MASK)
    if relative is None:
        return Snippet(
            shown_path, line, end, "unavailable", reason="not a repository path"
        )
    if line < 1:
        return Snippet(relative, line, end, "unavailable", reason="no line number")
    base = root.resolve()
    target = base / relative
    try:
        if target.is_symlink() or not target.is_file():
            return Snippet(
                relative, line, end, "unavailable", reason="not a regular file"
            )
        if not target.resolve().is_relative_to(base):
            return Snippet(
                relative, line, end, "unavailable", reason="outside the checkout"
            )
        if target.stat().st_size > _MAX_FILE_BYTES:
            return Snippet(relative, line, end, "unavailable", reason="file too large")
        raw = target.read_bytes()
    except OSError as exc:
        return Snippet(
            relative, line, end, "unavailable", reason=f"unreadable: {exc.strerror}"
        )
    if b"\0" in raw:
        return Snippet(relative, line, end, "unavailable", reason="binary file")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return Snippet(relative, line, end, "unavailable", reason="not UTF-8 text")
    lines = text.splitlines()
    if line > len(lines):
        return Snippet(
            relative,
            line,
            end,
            "unavailable",
            reason=f"line {line} is beyond the end of the file ({len(lines)} lines)",
        )
    end = min(end, len(lines))
    first = max(1, line - context)
    last = min(len(lines), end + context)
    rendered = tuple(
        SnippetLine(
            number=number,
            text=_clip(lines[number - 1]),
            offending=line <= number <= end,
        )
        for number in range(first, last + 1)
    )
    return Snippet(relative, line, end, "rendered", lines=rendered)


def _clip(text: str) -> str:
    text = text.replace("\t", "    ").rstrip()
    return text if len(text) <= _MAX_LINE_CHARS else text[: _MAX_LINE_CHARS - 1] + "…"


def is_sensitive(provider_id: str) -> bool:
    return provider_id.lower() in SENSITIVE_PROVIDERS


@dataclass(frozen=True, slots=True)
class FindingReport:
    """One finding as Core's payload reports it (field names agreed with L2)."""

    rule_id: str
    path: str
    line: int
    end_line: int
    message: str
    snippet: Snippet

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "path": self.path,
            "line": self.line,
            "end_line": self.end_line,
            "message": self.message,
            "snippet": self.snippet.to_dict(),
        }


def report_findings(
    root: Path, findings: Iterable[Finding], *, cap: int = SUBJECT_CAP
) -> tuple[tuple[FindingReport, ...], int]:
    """Up to ``cap`` located findings, sorted by path and line, and how many more.

    A finding without a location is not reported here; its rule and ID are in
    the gate reasons. A sensitive provider's message is replaced by the mask
    too, since a scanner may quote the secret in it.
    """
    reports: list[FindingReport] = []
    for finding in findings:
        location = finding.locations[0] if finding.locations else None
        if location is None or location.start_line is None:
            continue
        start = location.start_line
        sensitive = is_sensitive(finding.provider_id)
        snippet = render_snippet(
            root,
            location.normalized_path,
            start,
            location.end_line,
            sensitive=sensitive,
        )
        reports.append(
            FindingReport(
                rule_id=finding.canonical_rule_id or finding.provider_rule_id,
                path=snippet.path,
                line=start,
                end_line=snippet.end_line,
                message=MASK if sensitive else finding.message,
                snippet=snippet,
            )
        )
    reports.sort(key=lambda item: (item.path, item.line, item.rule_id))
    return tuple(reports[:cap]), max(0, len(reports) - cap)


def render_findings(
    root: Path, findings: Iterable[Finding], *, cap: int = SUBJECT_CAP
) -> str:
    """Text for a log or step summary: ``rule_id path:line`` and its snippet each."""
    reports, omitted = report_findings(root, findings, cap=cap)
    blocks = [
        f"{item.rule_id} {item.path}:{item.line}\n{item.snippet.render()}"
        for item in reports
    ]
    if omitted:
        blocks.append(f"+{omitted} more")
    return "\n\n".join(blocks)


__all__ = [
    "MASK",
    "SENSITIVE_PROVIDERS",
    "SNIPPET_CONTEXT",
    "FindingReport",
    "Snippet",
    "SnippetLine",
    "is_sensitive",
    "render_findings",
    "render_snippet",
    "report_findings",
]
