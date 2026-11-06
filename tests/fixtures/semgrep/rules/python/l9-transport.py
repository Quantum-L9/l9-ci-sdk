# Regression fixture for l9_ci/rulesets/semgrep/python/l9-transport.yml.
#
# Run with: semgrep --test --config l9_ci/rulesets/semgrep/python \
#               tests/fixtures/semgrep/rules/python
# (tests/rulesets/test_semgrep_rule_fixtures.py does exactly this.)
#
# AST-TRANSPORT-004 reports a raw json= body sent to an execution boundary (an
# L9 node/peer/Gate destination or /execute route). A JSON body sent to a
# third-party API is not an execute contract: the HubSpot search that blocked
# Quantum-L9/Enrichment.Inference.Engine at 12d8b351 must stay quiet. Scan
# INPUT only, never imported, and listed in .semgrepignore.
# ruff: noqa
# type: ignore
import httpx
import requests
from l9_core.routes import EXECUTE_URL
# ruleid: l9.transport.packet-envelope-import
from l9_legacy.packets import PacketEnvelope


def eie_12d8b351_hubspot(url, body, headers):
    # app/services/crm/hubspot_client.py
    # ok: l9.transport.raw-execute-dict-contract
    httpx.post(url, json=body, headers=headers, timeout=30)
    # ok: l9.transport.raw-execute-dict-contract
    requests.post("https://api.hubapi.com/crm/v3/objects/search", json=body)


def boundary_bodies(settings, base, packet, task):
    # A TransportPacket boundary object is the allowed body.
    # ok: l9.transport.raw-execute-dict-contract
    httpx.post(f"{settings.ceg_url}/v1/execute", json=packet)
    # An actual raw dict execute contract MUST be reported.
    # ruleid: l9.transport.raw-execute-dict-contract
    httpx.post(f"{settings.ceg_url}/v1/execute", json={"action": "match", "payload": task})
    # ruleid: l9.transport.raw-execute-dict-contract
    requests.post(base + EXECUTE_URL, json=task)
    # ruleid: l9.transport.raw-execute-dict-contract
    requests.post("http://ceg:8000/v1/execute", json={})
    # ruleid: l9.transport.raw-execute-dict-contract
    httpx.request("POST", settings.gate_url, json={"task": task})
    with httpx.Client() as client:
        # ruleid: l9.transport.raw-execute-dict-contract
        client.put(url=settings.peer_node_url, json=task)


def other_transport_rules(task):
    # ruleid: l9.transport.packet-envelope-instantiation
    PacketEnvelope(payload=task)
    # ruleid: l9.transport.alternate-packet-contract
    AgentPacket(payload=task)
