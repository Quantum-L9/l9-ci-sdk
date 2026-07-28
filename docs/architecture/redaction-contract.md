# Redaction Contract
Canonical artifacts must not retain:
- source snippets;
- Semgrep `extra.lines`;
- metavariable values;
- secret values;
- API tokens;
- private keys;
- absolute paths;
- complete environment variables;
- raw scanner objects.
Allowlisted metadata may include:
- CWE identifiers;
- OWASP identifiers;
- category;
- confidence label;
- technology;
- references;
- vulnerability class.
Artifact validation includes a defensive redaction scan.
The redaction scan is not a substitute for provider-specific allowlisting.
