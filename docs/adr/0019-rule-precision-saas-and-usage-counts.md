# ADR 0019: Rules Distinguish L9 Destinations, Usage Counts, Constant SQL and Real Handlers
## Status
Accepted. Amends the logging clause of
[ADR-0018](0018-rule-precision-by-code-position-and-dispatch.md) and supersedes
the "AST-ROUTING-001/002 flag the dispatch itself regardless of how the path
was built" clause of [ADR-0015](0015-packaged-rule-precision.md).
## Context
With ADR-0018 in place, `Quantum-L9/Enrichment.Inference.Engine` at `12d8b351`
still failed the required `Analyze (central Core)` check with 26 SDK-rule
findings (SDK `6d70e829`, Semgrep 1.171.0). Each was read at file:line and
each was a false positive:

- **16 × AST-LOGGING-001/002.** Every one logged an LLM usage figure:
  `tokens=total_tokens`, `prompt_tokens=usage.get("prompt_tokens")`,
  `tokens_used=response.tokens_used`. ADR-0018 already recorded the cause as an
  accepted gap: the secret-name regex matches the substring `token`.
- **5 × L9-PYTHON-SQL-STRING-FORMAT.** Alembic DDL,
  `op.execute(f"... DROP CONSTRAINT IF EXISTS {_OLD_UNIQUE}")`, where every
  interpolation is a module constant bound to a string literal. The f-string
  form reported any f-string at all.
- **2 × AST-ROUTING-002 and 1 × AST-TRANSPORT-004.** A Salesforce OAuth token
  request and a HubSpot CRM search. The rules matched every `httpx.post` /
  `requests.post`, and every `json=` body, whatever the destination.
- **2 × AST-HANDLER-002.** A Perplexity HTTP client,
  `query_perplexity(payload, api_key)`, and an inner concurrency helper. The
  rule matched any `async def` whose first parameter is `payload`, `input` or
  `data`.

Required CI must not fail on a false positive, and a precision change must not
buy that by losing a true positive.

## Decision
- **Logging (001, 002, 003):** each secret-name condition also rejects a name
  in an explicit token-COUNT form: `<q>_tokens` (plural only) for `total`,
  `prompt`, `completion`, `input`, `output`, `reasoning`, `max`, `num`, `n`;
  `tokens_used / _count / _total / _budget / _limit / _usage / _per_<x>`,
  `token_count`; the `tokenize` family. The exemption is void when the name
  also carries a credential qualifier (`access`, `refresh`, `auth`, `bearer`,
  `session`, `oauth`, `jwt`, `csrf`, `id_token`, `api_token`, `client`,
  `private`, `signing`, `reset`, `verif…`, `invite`, `magic`, `personal`, or any
  other secret word). Ambiguous qualifiers (`cached_tokens`, `generated_tokens`,
  `used_tokens`, singular `input_token`) are not exempt. In 002, a bare
  `tokens=` keyword is exempt only when its value is itself a proven count
  (an integer literal, `len()`/`sum()`, or a dotted name in a count form).
- **SQL f-string:** reported unless every expression inside the f-string is a
  string constant by Semgrep's constant propagation. The proof is the value,
  never the name, so an `UPPER_CASE` name holding input is still reported, as
  is any call, attribute, conversion (`{x!r}`), format spec (`{x:>10}`) or
  self-documenting (`{x=}`) interpolation of a non-constant. The `%` and
  `.format()` forms are unchanged.
- **Routing (001, 002) and transport (004):** taint rules over the destination.
  A source is a literal service URL on the node port or a `*.internal` host, an
  `/execute` route, or a name, attribute or setting/env key shaped like
  `<node|nodes|peer|peers|gate|ceg|eie|constellation|chassis|…>_url /
  _endpoint / _host`. Taint flows through concatenation, f-strings, locals and
  calls such as `os.getenv("GATE_URL")`. Sinks are the target of
  `post/put/patch/request/stream` (and `url=`) on the `requests` / `httpx`
  modules and on `requests.Session` / `httpx.Client` / `httpx.AsyncClient`
  instances created in scope. AST-TRANSPORT-004 additionally requires a
  `json=` body that is not `packet`.
- **AST-ROUTING-003:** the `.internal` alternative was written `\\.` inside
  single quotes, which YAML keeps verbatim, so it required a literal backslash
  and never matched. One backslash escapes the dot.
- **Handler (002):** the packet-slot shape is unchanged; the function must
  also be a handler by name (`handle`, `handler`, `handle_<x>`, `<x>_handler`),
  by a handler-registration decorator, or by a register/handler call in the
  same module. Decorated functions, which the plain `async def` pattern never
  matched, are matched explicitly.

## Consequences
- Rule identity is unchanged: no `id`, `metadata.l9.canonical_rule_id` or
  L9_META header changed (ADR-0003). This is a precision change.
- Witness scan, raw `semgrep scan` of the candidate vs. the `6d70e829` ruleset
  over EIE `12d8b351`, Cognitive.Engine.Graphs `9eddf39b`, l9-ci-core
  `0f8c399f`, l9-ci-sdk `6d70e829` and l9-constellation-topology `c533e7da`,
  matched by rule, file and line: the 26 EIE findings are removed and no other
  finding is removed. Two findings are added, both in topology
  `evidence/live-qualify-2026-08-02/run_gate_qualify.py:89`: a raw dict posted
  from an `httpx.AsyncClient` straight to `f"{GATE_URL}/v1/execute"`. That is a
  real Gate bypass, already acknowledged there for AST-ROUTING-004 by a
  rule-scoped `nosemgrep` (sealed evidence harness, topology ADR-0032); the
  owner extends that suppression or accepts the findings.
- **Supersedes ADR-0015's structural-coverage clause.** AST-ROUTING-001/002 no
  longer report a dispatch whose destination carries no L9 marker anywhere in
  its visible data flow, for example a URL received as an untyped parameter.
  That is the price of not reporting third-party HTTP. An `/execute` dispatch
  is still reported by AST-ROUTING-004 from any client.
- Detection widens where the old forms were blind: `put/patch/request/stream`
  and `url=` dispatch, Session/Client/AsyncClient instances, `*.internal`
  hosts, decorated handlers, and f-string SQL with conversions or format specs
  inside an `execute(f"...", params)` call.
- Accepted gaps: a node client held on `self` and created in another method is
  out of scope for the instance sinks; a handler registered only from another
  module under a non-handler name is not recognised; `{CONST + "x"}` stays
  reported because Semgrep does not fold it to a constant.
- Boundary cases are `semgrep --test` fixtures under
  `tests/fixtures/semgrep/rules/python/` (`l9-logging.py`, `l9-routing.py`, and
  the new `l9-baseline-security.py`, `l9-transport.py`,
  `l9-handler-signature.py`), each pinning the EIE false positives as `# ok:`
  next to at least one `# ruleid:` true positive per narrowed rule.
- Consumers inherit the correction when Core advances its pinned SDK revision
  (ADR-0016, ADR-0017).
