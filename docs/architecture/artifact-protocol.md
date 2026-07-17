# Artifact Protocol
The canonical protocol is:
```text
l9.finding-bundle/v1

The bundle is the authoritative SDK output.

Artifact layout

artifacts/
├── raw/
│   └── <provider>/
└── l9/
    └── finding-bundle.json

Raw provider reports and canonical artifacts must remain separate.

Required bundle sections

* schema
* schema_version
* SDK_version
* generated_at
* snapshot
* providers
* evidence
* findings
* classifications
* provider_failures
* coverage
* limitations
* summary

Referential integrity

Every finding evidence reference must resolve to an evidence record.

Every classification reference must resolve to a finding.

Every requested provider must have exactly one coverage record.

Atomic writes

Artifact writers must write to a temporary file, flush the file, and replace
the destination atomically.
