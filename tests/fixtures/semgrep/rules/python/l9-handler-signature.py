# Regression fixture for l9_ci/rulesets/semgrep/python/l9-handler-signature.yml.
#
# Run with: semgrep --test --config l9_ci/rulesets/semgrep/python \
#               tests/fixtures/semgrep/rules/python
# (tests/rulesets/test_semgrep_rule_fixtures.py does exactly this.)
#
# AST-HANDLER-002 reports a HANDLER whose packet slot is a raw payload/input
# dictionary. Ordinary functions with a `payload` parameter are not handlers:
# the two that blocked Quantum-L9/Enrichment.Inference.Engine at 12d8b351 must
# stay quiet. Scan INPUT only, never imported, and listed in .semgrepignore.
# ruff: noqa
# type: ignore
import asyncio
from typing import Any

from constellation_node_sdk.runtime.handlers import register_handler


# app/services/perplexity_client.py: an HTTP client, not a handler.
# ok: l9.handler.raw-payload-parameter
async def query_perplexity(
    payload: dict[str, Any],
    api_key: str,
    breaker=None,
    timeout: float = 60,
) -> dict:
    return {}


async def waterfall(max_concurrent: int):
    sem = asyncio.Semaphore(max_concurrent)

    # app/services/enrichment/waterfall_engine.py: an inner helper.
    # ok: l9.handler.raw-payload-parameter
    async def _call_variation(payload: dict) -> dict | None:
        async with sem:
            return await query_perplexity(payload=payload, api_key="")

    return _call_variation


# A non-handler decorator does not make a handler.
@functools.cache
# ok: l9.handler.raw-payload-parameter
async def cached_lookup(data: dict) -> dict:
    return data


# A real handler with a raw payload slot MUST be reported.
# ruleid: l9.handler.raw-payload-parameter
async def handle_enrich(payload: dict) -> dict:
    return {}


# ruleid: l9.handler.raw-payload-parameter
async def enrich_handler(input: dict[str, Any]) -> dict:
    return {}


# ruleid: l9.handler.raw-payload-parameter
async def handler(data: dict) -> dict:
    return {}


# ruleid: l9.handler.raw-payload-parameter
@register_handler("match")
async def match(payload: dict) -> dict:
    return {}


# ruleid: l9.handler.raw-payload-parameter
@router.handler("score")
async def score(payload: dict) -> dict:
    return {}


# A decorated handler was invisible to the plain `async def` pattern.
# ruleid: l9.handler.raw-payload-parameter
@traced
async def handle_sync(payload: dict) -> dict:
    return {}


# ruleid: l9.handler.raw-payload-parameter
async def writeback(payload: dict) -> dict:
    return {}


register_handler("writeback", writeback)


# The TransportPacket packet slot is the contract.
# ok: l9.handler.raw-payload-parameter
async def handle_transport(packet: TransportPacket) -> TransportPacket:
    return packet


# The other handler-signature rules are unchanged.
# ruleid: l9.handler.dict-packet-parameter
async def route(packet: dict) -> dict:
    return packet


# ruleid: l9.handler.missing-transportpacket-return
async def handler(packet: TransportPacket) -> dict:
    return {}
