# ADR 0018: Logging and Routing Rules Match Code Positions and Outbound Dispatch
## Status
Accepted. Amends the routing and logging clauses of
[ADR-0015](0015-packaged-rule-precision.md).
## Context
ADR-0015 required a packaged rule to constrain what it claims to match, and
settled two precision bugs. Organization CI then made these rules blocking in
required checks (`Analyze (central Core)`, `pr_fast` profile), and two rules
still failed correct code:

- `l9.logging.forbidden-secret-field` (AST-LOGGING-001) bound `$SECRET` to
  any logger argument and applied the secret-name regex to its source text.
  A string literal is an argument too, so message prose failed the gate with
  no secret logged: `"Failed to decode JWT claims from token"`,
  `"L9_API_KEY is not set or uses a default value"`. AST-LOGGING-002/003 had
  the same prose bug in regex form and matched single-line calls only.
- `l9.routing.gateclient-bypass-execute` (AST-ROUTING-004) kept ADR-0015's
  `pattern-regex` over any string literal ending at `/execute`. That cannot
  tell a node's own ingress from an outbound call, so it failed
  `@application.post("/v1/execute", ...)` and an inbound comparison against
  `request.url.path`. Every node defines that path for its ingress.

Required CI must not fail on a false positive.

## Decision
- **Logging (001):** a secret-like word matches only in a code position
  inside the argument: a name, an attribute, a subscript key, a dict key, a
  nested call's keyword, or a name-shaped (spaceless) literal passed to a
  nested call such as `os.getenv("TOKEN")`. Keyword values (for example
  `extra={...}`) are inspected too. A secret inside an f-string is left to
  003, so one leak yields one finding.
- **Logging (002, 003):** 002 matches a secret-like keyword name on the
  logger call itself; 003 matches a secret name in an f-string's interpolated
  expression, in any argument position, across lines.
- **Routing (004):** a taint rule replaces the regex. Sources are a literal
  ending in `/execute` or `/v1/execute`, or an `EXECUTE_*`-shaped name
  (including imported ones). Sinks are the target argument of outbound
  `.post/.put/.patch/.request/.send/.stream` calls. Route decorators are
  excluded by reusing the call's own client and method, so a dispatch made
  inside a decorated handler is still reported.
- **This supersedes ADR-0015's routing clause.** A bare routing constant
  (`EXECUTE_PATH = "/v1/execute"`) is no longer a finding on its own; it is
  reported where it reaches a dispatch.
- **Supersedes ADR-0015's pinning mechanism for these rules.** Boundary cases
  are now `semgrep --test` fixtures under `tests/fixtures/semgrep/rules/python/`
  (`# ruleid:` / `# ok:`). They run in self-CI's `semgrep rule fixtures` job and in
  `tests/rulesets/test_semgrep_rule_fixtures.py`. Semgrep-free guards in
  `tests/rulesets/test_packaged_rule_metadata_shape.py` fail if any of these
  rules returns to text matching.

## Consequences
- Rule identity is unchanged: no `id` or `metadata.l9.canonical_rule_id`
  changed (ADR-0003). This is a precision change.
- Detection widens where the old forms were blind: `extra=` secrets,
  multi-line keyword secrets, a constant used to build a dispatch URL,
  imported `EXECUTE_URL`, `.request/.stream/.send`, and dispatch inside a
  decorated handler.
- Accepted gap: a secret logged under an innocent variable name with
  secret-labelled prose (`"password: %s", pw`) is not caught by 001, which
  sees names, not prose. A taint-based rule can close it later.
- Accepted gap: the secret-name regex still matches substrings
  (`token_count`), and `self.logger.*` / `log.*` receivers are not covered.
- Consumers inherit the correction when Core advances its pinned SDK
  revision (ADR-0016, ADR-0017).
