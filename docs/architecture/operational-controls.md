# Operational Controls
Provider execution and report import are bounded operations.
## Default limits
- provider timeout: 900 seconds
- process output: 10 MiB
- provider report: 100 MiB
- findings: 100,000
- evidence records: 200,000
## Failure behavior
Limit violations are explicit failures.
Reports are never silently truncated and normalized.
Console stdout and stderr may be truncated only in diagnostic failure records,
and must never contain secrets.
## Environment
Provider execution uses an allowlisted environment.
Core supplies additional environment values explicitly.
