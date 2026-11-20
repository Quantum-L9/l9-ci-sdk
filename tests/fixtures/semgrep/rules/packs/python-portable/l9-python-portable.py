"""semgrep --test fixture for the harvested python-portable pack.

Pairs with l9_ci/rulesets/semgrep/packs/python-portable/l9-python-portable.yml.
Every line annotated ``ruleid`` must be flagged and every line annotated
``ok`` must not.

The float and singleton cases are the Quantum-L9/Cognitive.Engine.Graphs
fixture .semgrep/fixtures/semgrep-rules.py at
073aa051e9d68ffcfadb736fc58ab6192276c8cd (blob
36fc93e1fa6ab12c289cab93ce4e2e10cb09806c), with the rule IDs renamed to the
SDK derivatives. The datetime and httpx cases are written here: neither donor
carries a fixture for those two rules.

Scan input only. Never imported or executed.
"""

import json
import math
import os
import sys
import threading
from datetime import UTC, datetime

import httpx
import numpy as np


def env_threshold() -> float:
    # ruleid: l9.python.portable.float-of-untrusted-input-unguarded
    return float(os.environ["CEG_THRESHOLD"])


def env_default() -> float:
    # ruleid: l9.python.portable.float-of-untrusted-input-unguarded
    return float(os.getenv("CEG_ALPHA", "0.5"))


def argv_value() -> float:
    # ruleid: l9.python.portable.float-of-untrusted-input-unguarded
    return float(sys.argv[1])


def parsed(text: str) -> float:
    doc = json.loads(text)
    # ruleid: l9.python.portable.float-of-untrusted-input-unguarded
    return float(doc["score"])


async def handle_thing(tenant: str, payload: dict) -> dict:
    raw = payload.get("weight", "0")
    # ruleid: l9.python.portable.float-of-untrusted-input-unguarded
    weight = float(raw)
    return {"weight": weight}


async def handle_guarded(tenant: str, payload: dict) -> dict:
    try:
        # ok: l9.python.portable.float-of-untrusted-input-unguarded
        weight = float(payload["weight"])
    except (ValueError, TypeError):
        weight = 0.0
    return {"weight": weight}


def literal_probe(expr: str) -> bool:
    try:
        # ok: l9.python.portable.float-of-untrusted-input-unguarded
        float(expr)
    except ValueError:
        return False
    else:
        return True


def numeric_only(scores: list[float], row: np.ndarray) -> list[float]:
    # ok: l9.python.portable.float-of-untrusted-input-unguarded
    a = float(np.mean(scores))
    # ok: l9.python.portable.float-of-untrusted-input-unguarded
    b = float(row[0] * 2.0)
    # ok: l9.python.portable.float-of-untrusted-input-unguarded
    c = float("inf")
    # ok: l9.python.portable.float-of-untrusted-input-unguarded
    d = float(math.sqrt(a))
    return [a, b, c, d]


async def handle_cast(tenant: str, payload: dict) -> dict:
    count = int(payload["count"])
    # ok: l9.python.portable.float-of-untrusted-input-unguarded
    return {"ratio": float(count) / 2}


# --- singleton-init-without-lock ---

_client = None
_lock = threading.Lock()


def make() -> object:
    return object()


def unlocked_global() -> object:
    global _client
    # ruleid: l9.python.portable.singleton-init-without-lock
    if _client is None:
        _client = make()
    return _client


def locked_global() -> object:
    global _client
    with _lock:
        # ok: l9.python.portable.singleton-init-without-lock
        if _client is None:
            _client = make()
    return _client


class Registry:
    instance: object | None = None
    cache: object | None = None

    @classmethod
    def get(cls) -> object:
        # ruleid: l9.python.portable.singleton-init-without-lock
        if cls.instance is None:
            cls.instance = make()
        return cls.instance

    @staticmethod
    def get_static() -> object:
        # ruleid: l9.python.portable.singleton-init-without-lock
        if Registry.instance is None:
            Registry.instance = make()
        return Registry.instance

    def lazy(self) -> object:
        # ok: l9.python.portable.singleton-init-without-lock
        if self.cache is None:
            self.cache = make()
        return self.cache


def local_default(k: object = None) -> object:
    # ok: l9.python.portable.singleton-init-without-lock
    if k is None:
        k = make()
    return k


# --- datetime-utcnow ---


def naive_now() -> datetime:
    # ruleid: l9.python.portable.datetime-utcnow
    return datetime.utcnow()


def aware_now() -> datetime:
    # ok: l9.python.portable.datetime-utcnow
    return datetime.now(UTC)


def from_timestamp(stamp: float) -> datetime:
    # ok: l9.python.portable.datetime-utcnow
    return datetime.fromtimestamp(stamp, tz=UTC)


# --- httpx-async-client-without-context ---


async def leaked_client(url: str) -> int:
    # ruleid: l9.python.portable.httpx-async-client-without-context
    client = httpx.AsyncClient()
    response = await client.get(url)
    return response.status_code


async def managed_client(url: str) -> int:
    # ok: l9.python.portable.httpx-async-client-without-context
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    return response.status_code


def sync_client(url: str) -> int:
    # ok: l9.python.portable.httpx-async-client-without-context
    client = httpx.Client()
    return client.get(url).status_code
