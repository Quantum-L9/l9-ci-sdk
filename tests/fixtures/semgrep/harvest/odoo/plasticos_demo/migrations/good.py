"""Known-good counterpart of plasticos_demo/migrations/bad.py.

Scan input only. Never imported or executed.
"""


def migrate(cr, version):
    # good: plasticos-destructive-migration-sql-py
    cr.execute("ALTER TABLE plasticos_demo ADD COLUMN note varchar")
