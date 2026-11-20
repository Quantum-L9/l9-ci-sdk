"""Known-bad and known-good cases for donor rules compared with the SDK baseline.

A ``# bad: <donor rule id>`` comment says the next line must be flagged by
that donor rule. A ``# good: <donor rule id>`` comment says it must not.
scripts/harvest_donor_evidence.py runs the donor rule files and the SDK
packs over this file and reports, per rule, which marked lines matched.

Scan input only. Never imported or executed.
"""

import logging
import pickle

import structlog


def evaluates(expression: str) -> object:
    # bad: no-eval
    return eval(expression)


def evaluates_frame(frame: object) -> object:
    # good: no-eval
    return frame.eval("a + b")


def loads_pickle(blob: bytes) -> object:
    # bad: no-pickle-loads
    return pickle.loads(blob)


def dumps_pickle(value: object) -> bytes:
    # good: no-pickle-loads
    return pickle.dumps(value)


def builds_sql(table: str) -> str:
    # bad: no-sql-fstring
    return f"SELECT id FROM {table} WHERE active"


def runs_sql(cursor: object, table: str) -> None:
    # bad: no-sql-fstring
    cursor.execute(f"DELETE FROM {table} WHERE id = 1")


def constant_sql() -> str:
    # good: no-sql-fstring
    return "SELECT id FROM account WHERE id = %s"


def structlog_child() -> object:
    logger = structlog.get_logger("svc")
    # bad: no-structlog-getchild
    return logger.getChild("worker")


def stdlib_child() -> logging.Logger:
    # A stdlib logger has getChild; this call is correct Python.
    # good: no-structlog-getchild
    return logging.getLogger("svc").getChild("worker")
