# Donor rule harvest

`semgrep-donor-ledger.yaml` has one row for each of the 59 Semgrep rules found
at four consumers on 2026-11-20. A row is evidence for a decision the owner
makes. It admits nothing and retires nothing: every donor rule stays in place
until Core proves a central successor in a live canary (`L9-CI-CORE-004`).

| Donor | Rules | `promote_language` | `already_satisfied` | `retain_domain` | `defer_unknown` |
| --- | --- | --- | --- | --- | --- |
| `Quantum-L9/Enrichment.Inference.Engine` | 8 | 2 | 2 | 0 | 4 |
| `Quantum-L9/Cognitive.Engine.Graphs` | 8 | 4 | 2 | 0 | 2 |
| `Quantum-L9/Cursor-Governance` | 4 | 0 | 0 | 3 | 1 |
| `cryptoxdog/IB-Odoo_19` | 39 | 0 | 4 | 11 | 24 |
| Total | 59 | 6 | 8 | 14 | 31 |

What the evidence showed:

- The Enrichment.Inference.Engine and Cognitive.Engine.Graphs files share
  eight rule IDs. Six pairs have identical patterns. Two do not:
  `singleton-requires-lock` and `float-requires-try-except` have the same ID
  and different behaviour. The Cognitive.Engine.Graphs forms are carried into
  the SDK; the Enrichment.Inference.Engine forms flag lines the shared fixture
  marks correct, so they are not consolidated.
- `no-sql-fstring` flagged neither known-bad line in either donor. Its
  intended behaviour was not reproduced.
- `no-structlog-getchild` also flags `getChild` on a standard-library logger.
- Four carried rules form the candidate `python-portable` pack, in shadow
  mode, outside every `l9-ci semgrep run` profile.
- No Odoo rule was carried. `cryptoxdog/IB-Odoo_19` has no licence file and a
  different account owner, so the right to carry a derivative is unresolved.
  The Odoo 19 SQL, model and XML rules are `defer_unknown` with
  `promote_framework` named as the target once that is resolved. Rules that
  encode PlasticOS decisions are `retain_domain`.
- The three Cursor-Governance memory-boundary rules are `retain_domain` and
  stay path-scoped at their owner.

Rules that stay at their owner are not in this repository, so the SDK's CI
cannot re-run their evidence. `scripts/harvest_donor_evidence.py` re-runs all
of it from donor checkouts.
