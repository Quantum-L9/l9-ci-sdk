"""Known-bad case for the path-scoped destructive-migration rule.

Scan input only. Never imported or executed.
"""


def migrate(cr, version):
    # bad: plasticos-destructive-migration-sql-py
    cr.execute("DROP TABLE plasticos_demo_legacy")
