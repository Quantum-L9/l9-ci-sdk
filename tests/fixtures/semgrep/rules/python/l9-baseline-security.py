# Regression fixture for l9_ci/rulesets/semgrep/python/l9-baseline-security.yml
# (L9-PYTHON-SQL-STRING-FORMAT, l9.baseline.python.sql-string-format).
#
# Run with: semgrep --test --config l9_ci/rulesets/semgrep/python \
#               tests/fixtures/semgrep/rules/python
# (tests/rulesets/test_semgrep_rule_fixtures.py does exactly this.)
#
# Lines annotated ruleid are dynamic SQL the rule MUST flag; lines annotated ok
# are the false positives that blocked Quantum-L9/Enrichment.Inference.Engine at
# 12d8b351 (migrations/versions/002_tenant_scoped_idempotency.py) and must stay
# quiet. The proof of safety is a constant VALUE, never an UPPER_CASE name.
# Scan INPUT only, never imported, and listed in .semgrepignore.
# ruff: noqa
# type: ignore
from alembic import op

_OLD_UNIQUE = "enrichment_results_idempotency_key_key"
_KEY_INDEX = "ix_enrichment_results_idempotency_key"
# An UPPER_CASE name is not a trust proof.
TABLE_FROM_USER = input()


def eie_12d8b351_migration_constants():
    # ok: l9.baseline.python.sql-string-format
    op.execute(
        f"ALTER TABLE enrichment_results DROP CONSTRAINT IF EXISTS {_OLD_UNIQUE}"
    )
    # ok: l9.baseline.python.sql-string-format
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {_KEY_INDEX} ON enrichment_results (idempotency_key)"
    )
    # ok: l9.baseline.python.sql-string-format
    op.execute(
        f"ALTER TABLE enrichment_results ADD CONSTRAINT {_OLD_UNIQUE} UNIQUE (idempotency_key)"
    )
    # ok: l9.baseline.python.sql-string-format
    op.execute(f"DROP INDEX IF EXISTS {_KEY_INDEX!s}")
    # A static f-string interpolates nothing.
    # ok: l9.baseline.python.sql-string-format
    op.execute(f"SELECT 1")


def parameterized(cursor, user_id):
    # ok: l9.baseline.python.sql-string-format
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))


def must_still_catch(cursor, user, request, query):
    LOCAL_UPPER = request.args["table"]
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(f"SELECT * FROM users WHERE name = '{user}'")
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(f"DROP TABLE {TABLE_FROM_USER}")
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(f"DROP TABLE {LOCAL_UPPER}")
    # One constant does not vouch for the rest.
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(f"ALTER TABLE {_KEY_INDEX} RENAME TO {user}")
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(f"SELECT {user.name} FROM t")
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(f"SELECT {user!r}")
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(f"SELECT {user:>10}")
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(f"SELECT {user=}")
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(f"SELECT * FROM t LIMIT {len(user)}")
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(f"DELETE FROM t WHERE id = {request.args['id']}", ())
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(f"SELECT * FROM t WHERE a = {user} " "AND b = 1")  # fmt: skip
    # ruleid: l9.baseline.python.sql-string-format
    op.execute(f"DROP INDEX {_KEY_INDEX + user}")
    # The % and .format() forms are unchanged.
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(query % (user,))
    # ruleid: l9.baseline.python.sql-string-format
    cursor.execute(query.format(user))
