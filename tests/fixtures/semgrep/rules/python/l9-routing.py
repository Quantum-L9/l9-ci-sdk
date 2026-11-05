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
