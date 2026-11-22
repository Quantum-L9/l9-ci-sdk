# ADR 0024: A registry finding is withheld where the code declares a non-security use

## Status
Accepted (CTO, 2026-11-21: SHA-1 git-object-id precision).

**Decision owner:** `Quantum-L9/l9-ci-sdk`. **Related:** ADR 0022 (registry
rule supersession), #141 (framework-scoped registry rules). Not a waiver: no
consumer can add entries, and nothing is keyed to a repository or a finding.

## Context

The community registry rule
`python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1`
blocked `hashlib.sha1` used to compute git object IDs in
`Quantum-L9/l9-semantic-compiler-engine` (`node_deploy.py`, `compiler.py`,
`registry.py`). The git object format requires SHA-1 there; nothing is
security-relevant. Python 3.9+ lets a caller say so:
`hashlib.sha1(..., usedforsecurity=False)`.

The registry MD5 rule already excludes `hashlib.md5(..., usedforsecurity=False, ...)`
with a `pattern-not`. The SHA-1 rule has no such exclusion: verified against
the rule source and against Semgrep 1.171.0, which reports the declared forms.

## Decision

1. `l9_ci/rulesets/semgrep/rule-precision.yaml`
   (`l9.semgrep-rule-precision/v1`) declares, per registry rule, the keyword
   whose literal `False` declares the non-security use. The first entry is
   the SHA-1 rule with `usedforsecurity`.
2. After the scan, `l9_ci.pipeline.precision` withholds a finding of a declared
   rule only when a call that starts on the finding's line passes that keyword
   as the literal `False`, read from the file's Python syntax tree. The
   evidence stays in the bundle and one limitation names every withheld site.
3. Everything that cannot be shown keeps the finding: an unreadable,
   oversized or unparseable file, `usedforsecurity=True`, a variable or
   expression instead of the literal, or no matching call.
4. A packaged L9 rule cannot be declared; it states its own precision in its
   pattern.

A heuristic "git object ID" pattern (a `blob <size>\0` header before the
digest) was considered and rejected: it guesses intent from data shape, while
the keyword is the caller's explicit, standard declaration.

## Consumer action

A repository that uses SHA-1 for a non-security purpose passes
`usedforsecurity=False` at the call. The keyword documents the intent in the
code, and Python itself then permits the call on FIPS-restricted builds.

## Compatibility

No contract changes: the finding bundle, its schema and the scan-scope
evidence are unchanged. A withheld finding is absent from `findings`, which
readers already handle; its evidence and a limitation stay.
