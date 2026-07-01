"""
L9_META
l9_schema: 1
origin: l9-ci-sdk
layer: [utils, source-scanning]
tags: [L9_CI, scanner-primitive, string-literal-aware]
owner: platform
status: active
/L9_META
"""

from __future__ import annotations


def docstring_line_numbers(text: str) -> set[int]:
    """Return the 1-based line numbers that fall inside triple-quoted strings.

    Line-based scanners that only skip lines *starting* with a triple quote still
    match a symbol mentioned inside a multi-line docstring body, producing false
    positives. This walks the source tracking triple-quote state so every line
    within a triple-quoted region is reported. It is a heuristic (it does not
    model triple quotes nested inside single-quoted strings) and only ever
    suppresses matches inside prose, never real code lines.
    """
    inside: set[int] = set()
    i, line, delim, n = 0, 1, "", len(text)
    while i < n:
        if delim:
            inside.add(line)
            if text[i : i + 3] == delim:
                delim = ""
                i += 3
                continue
        elif text[i : i + 3] in ('"""', "'''"):
            delim = text[i : i + 3]
            inside.add(line)
            i += 3
            continue
        if text[i] == "\n":
            line += 1
        i += 1
    return inside


def strip_string_and_comment_content(line: str) -> str:
    """Return ``line`` with the *contents* of single-line string literals and any
    trailing ``#`` comment removed, so an identifier scanner doesn't match a
    symbol that only appears inside prose (e.g. ``print("uses PacketEnvelope")``).

    Quote characters themselves are preserved as empty markers; real code tokens
    (imports, annotations, calls) are left untouched. This is a single-line
    heuristic — triple-quoted regions that span lines are handled separately by
    :func:`docstring_line_numbers`.
    """
    out: list[str] = []
    quote = ""
    escaped = False
    for ch in line:
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
                out.append(ch)
            continue
        if ch in ('"', "'"):
            quote = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out)
