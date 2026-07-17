# Version Negotiation
Compatibility is checked across three values:
1. artifact protocol;
2. artifact schema version;
3. SDK version.
## Artifact protocol
The supported finding protocol is:
```text
l9.finding-bundle/v1

An unsupported protocol is rejected.

Schema version

Readers accept schema version 1.x.x.

Schema major version 2 requires an explicit consumer upgrade.

SDK version

Core should pin an exact SDK release or commit.

Core may declare a minimum SDK version through:

l9-ci compatibility check \
  --bundle artifacts/l9/finding-bundle.json \
  --minimum-SDK-version 1.2.0

Version compatibility does not replace schema or semantic validation.
