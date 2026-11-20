"""Known-bad and known-good cases for the Cursor-Governance memory-boundary rules.

The same file is stored at cursor/svc/sample.py. The three memory-boundary
rules are path-scoped to the memory path, so they must flag this copy and
must stay silent on that one.

Scan input only. Never imported or executed.
"""

import json
import os
import subprocess

# bad: l9.memory-boundary-no-network-or-provider-transport
import requests


def read_token() -> str | None:
    # bad: l9.no-semgrep-app-token-in-child-env
    return os.environ.get("SEMGREP_APP_TOKEN")


def read_other() -> str | None:
    # good: l9.no-semgrep-app-token-in-child-env
    return os.environ.get("L9_MEMORY_NAMESPACE")


def fetch(url: str) -> int:
    return requests.get(url, timeout=5).status_code


def spawn_list() -> int:
    # bad: l9.memory-boundary-spawn-only-through-the-binding
    return subprocess.run(["l9-memory", "health"], check=False).returncode


def spawn_shell() -> int:
    # bad: l9.memory-boundary-no-shell-string-spawn
    return subprocess.call("l9-memory health", shell=True)


def encode(payload: dict[str, str]) -> str:
    # good: l9.memory-boundary-no-network-or-provider-transport
    # good: l9.memory-boundary-spawn-only-through-the-binding
    # good: l9.memory-boundary-no-shell-string-spawn
    return json.dumps(payload, sort_keys=True)
