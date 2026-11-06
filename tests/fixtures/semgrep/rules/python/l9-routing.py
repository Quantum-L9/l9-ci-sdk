# Regression fixture for l9_ci/rulesets/semgrep/python/l9-routing.yml
# (AST-ROUTING-004, l9.routing.gateclient-bypass-execute).
#
# Run with: semgrep --test --config l9_ci/rulesets/semgrep/python \
#               tests/fixtures/semgrep/rules/python
# (tests/rulesets/test_semgrep_rule_fixtures.py does exactly this.)
#
# Lines annotated ruleid are raw outbound /execute dispatch the rule MUST
# flag; lines annotated ok are a node's own ingress, which failed
# Quantum-L9/Cognitive.Engine.Graphs PR #409 and must stay quiet. semgrep
# --test requires every rule in the file's config to be annotated, so the
# sibling AST-ROUTING-001/002/003 findings are annotated alongside. Scan INPUT
# only, never imported, and listed in .semgrepignore.
# ruff: noqa
# type: ignore
import httpx
import requests
from fastapi import FastAPI
from l9_core.routes import EXECUTE_URL

application = FastAPI()
# The constant an ingress needs. Defining it dispatches nothing.
# ok: l9.routing.gateclient-bypass-execute
_EXECUTE_PATH = "/v1/execute"
# ok: l9.routing.gateclient-bypass-execute
EXECUTE_PATH = "/v1/execute"
# ok: l9.routing.gateclient-bypass-execute
PATH = "/execute"


# CEG chassis/chassis_app.py: the FastAPI route definition of the single ingress.
# ok: l9.routing.gateclient-bypass-execute
@application.post(
    "/v1/execute",
    response_model=dict,
)
async def execute(request):
    return {}


# ok: l9.routing.gateclient-bypass-execute
@application.api_route("/v1/execute", methods=["POST"])
async def execute_any(request):
    return {}


# ok: l9.routing.gateclient-bypass-execute
application.add_api_route("/v1/execute", execute, methods=["POST"])


# CEG chassis/node_app.py: comparing the INBOUND path against the constant.
async def dispatch(request, call_next):
    # ok: l9.routing.gateclient-bypass-execute
    if request.method != "POST" or request.url.path != _EXECUTE_PATH:
        return await call_next(request)
    return None


def prose():
    # ok: l9.routing.gateclient-bypass-execute
    files = ("references/execute.md",)
    # ok: l9.routing.gateclient-bypass-execute
    help_text = "Skip paste/execute; only copy lower Results grid"
    # Not an /execute target, but direct dispatch to a peer URL: the
    # sibling rules own it. (ok: l9.routing.gateclient-bypass-execute)
    # ruleid: l9.routing.requests-direct-node-dispatch, l9.routing.hardcoded-peer-node-url
    requests.post("http://gate:8000/v1/packets", json={})
    return files, help_text


def must_still_catch(base, client, session):
    # ruleid: l9.routing.gateclient-bypass-execute, l9.routing.requests-direct-node-dispatch, l9.routing.hardcoded-peer-node-url
    requests.post("http://node:8000/v1/execute", json={})
    # ruleid: l9.routing.gateclient-bypass-execute, l9.routing.httpx-direct-node-dispatch
    httpx.post(f"{base}/execute", json={})
    # ruleid: l9.routing.gateclient-bypass-execute
    client.put("/execute")
    # A module constant, later passed to a client call.
    # ruleid: l9.routing.gateclient-bypass-execute, l9.routing.requests-direct-node-dispatch
    requests.post(base + EXECUTE_PATH, json={})
    # ruleid: l9.routing.gateclient-bypass-execute
    client.post(f"{base}{EXECUTE_PATH}", json={})
    url = f"{base}/execute"
    # ruleid: l9.routing.gateclient-bypass-execute, l9.routing.httpx-direct-node-dispatch
    httpx.post(url, json={})
    # ruleid: l9.routing.gateclient-bypass-execute
    client.request("POST", f"{base}/v1/execute")
    # ruleid: l9.routing.gateclient-bypass-execute
    session.post(url=EXECUTE_PATH)
    # ruleid: l9.routing.gateclient-bypass-execute
    client.stream("POST", base + PATH)
    # A constant imported from another module, matched by its name.
    # ruleid: l9.routing.gateclient-bypass-execute
    client.post(base + EXECUTE_URL)


# A dispatch made from INSIDE a decorated handler is still a dispatch.
@application.post("/v1/forward")
async def forward(request, client):
    # ruleid: l9.routing.gateclient-bypass-execute
    return await client.post(EXECUTE_PATH, json={})


async def via_send(client, base):
    req = client.build_request("POST", f"{base}/v1/execute")
    # ruleid: l9.routing.gateclient-bypass-execute
    return await client.send(req)


# AST-ROUTING-001/002 report a requests/httpx dispatch only when its target is
# an L9 node/peer/Gate destination. The two calls that blocked
# Quantum-L9/Enrichment.Inference.Engine at 12d8b351 talk to third parties.
def eie_12d8b351_third_party_http(token_url, body, url, headers):
    # app/services/crm/salesforce_client.py: the Salesforce OAuth token request.
    # ok: l9.routing.httpx-direct-node-dispatch
    response = httpx.post(token_url, data=body, timeout=30)
    # app/services/crm/hubspot_client.py: the HubSpot CRM search.
    # ok: l9.routing.httpx-direct-node-dispatch
    response = httpx.post(url, json=body, headers=headers, timeout=30)
    # ok: l9.routing.requests-direct-node-dispatch
    requests.post("https://api.hubapi.com/crm/v3/objects/search", json=body)
    # Not an L9 gate, just a name that contains "gateway".
    # ok: l9.routing.httpx-direct-node-dispatch
    httpx.post(settings.api_gateway_url, json=body)
    # A read is not dispatch.
    # ok: l9.routing.httpx-direct-node-dispatch
    httpx.get(settings.gate_url)
    return response


def node_dispatch_by_destination(settings, os, payload, base):
    # A node call through a URL built from settings MUST be reported.
    # ruleid: l9.routing.httpx-direct-node-dispatch
    httpx.post(f"{settings.ceg_base_url}/v1/match", json=payload)
    # ruleid: l9.routing.httpx-direct-node-dispatch, l9.routing.gateclient-bypass-execute
    httpx.post(f"{settings.ceg_url}/v1/execute", json=payload)
    # ruleid: l9.routing.requests-direct-node-dispatch
    requests.post(settings.gate_url, json=payload)
    # ruleid: l9.routing.requests-direct-node-dispatch
    requests.put(os.environ["GATE_URL"] + "/v1/packets", json=payload)
    # ruleid: l9.routing.httpx-direct-node-dispatch
    httpx.patch(os.getenv("PEER_NODE_URL"), json=payload)
    node = settings.peer_node_url
    target = f"{node}/v1/match"
    # ruleid: l9.routing.requests-direct-node-dispatch
    requests.post(url=target, json=payload)
    # ruleid: l9.routing.requests-direct-node-dispatch, l9.routing.hardcoded-peer-node-url
    requests.request("POST", "http://ceg:8000/v1/match", json=payload)
    # The .internal alternative of AST-ROUTING-003 now matches.
    # ruleid: l9.routing.httpx-direct-node-dispatch, l9.routing.hardcoded-peer-node-url
    httpx.post("https://ceg.internal/v1/match", json=payload)
    # ruleid: l9.routing.httpx-direct-node-dispatch, l9.routing.gateclient-bypass-execute
    httpx.request("POST", f"{base}{EXECUTE_PATH}", json=payload)


async def node_dispatch_through_clients(settings, payload):
    async with httpx.AsyncClient() as http:
        # ruleid: l9.routing.httpx-direct-node-dispatch
        await http.post(f"{settings.gate_url}/v1/packets", json=payload)
        # ok: l9.routing.httpx-direct-node-dispatch
        await http.post("https://hooks.example.com/notify", json=payload)
    sync_client = httpx.Client()
    # ruleid: l9.routing.httpx-direct-node-dispatch
    sync_client.request("POST", settings.eie_url, json=payload)
    with requests.Session() as s:
        # ruleid: l9.routing.requests-direct-node-dispatch
        s.post(settings.node_endpoint, json=payload)
