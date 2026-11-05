# l9-ci-sdk repository-owned Make implementation.
#
# REPOSITORY-OWNED: hand-maintained, never generated. The root Makefile is the
# Core-owned make-v1 facade (Quantum-L9/l9-ci-core
# tools/l9_repo/facades/make-v1.mk), reproduced byte-for-byte and validated
# byte-for-byte by Core's repository verification. Never edit the Makefile; it
# owns help/setup/validate/check/test and includes this file. Do not define any
# of those five targets here.
#
#   make setup     repo-setup     .venv + CI toolchain + pre-commit (= deps)
#   make validate  repo-validate  governance JSON, action pins, yamllint,
#                                 tracked MANIFEST.md currency
#   make check     repo-check     ruff check, ruff format --check, mypy l9_ci
#                                 (non-mutating)
#   make test      repo-test      pytest -q $(PYTEST_ARGS)
#
# Core runs setup -> validate -> check -> test in that order on a plain runner.
# The pre-V2 meanings of the facade names this file used to define:
#
#   make check-full   the old `make check` (hooks + clean tree + mypy + pytest);
#                     `make gate`, `make ci`, `make push` and the pre-push hook
#                     still run it
#   make test         unchanged (now the repo-test leaf)
#   make help         now the facade's help; it lists every `##` target here
#
# Authority: .pre-commit-config.yaml (hooks) + requirements-ci.txt (toolchain).
# Ship path: make push  (also enforced by the git pre-push hook).

VENV        := $(CURDIR)/.venv
VENV_PYTHON := $(VENV)/bin/python
# Prefer repo venv when present; override with PYTHON=/path/to/python.
# Use recursive `=` (not `:=`) so ensure-toolchain can create .venv mid-run and
# later typecheck/test/hooks recipes still pick it up in the same make invocation.
ifeq ($(origin PYTHON),command line)
  PYTHON_OVERRIDE := $(PYTHON)
  PYTHON = $(PYTHON_OVERRIDE)
else
  PYTHON = $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python3)
endif
# Do not name this PRE_COMMIT — that env var is reserved/collides under hook runs.
ifeq ($(origin PRE_COMMIT_BIN),command line)
  PRE_COMMIT_BIN_OVERRIDE := $(PRE_COMMIT_BIN)
  PRE_COMMIT_BIN = $(PRE_COMMIT_BIN_OVERRIDE)
else
  PRE_COMMIT_BIN = $(if $(wildcard $(VENV)/bin/pre-commit),$(VENV)/bin/pre-commit,pre-commit)
endif
PYTEST_ARGS ?=
PUSH_ARGS   ?=

export PYTHONPATH := $(CURDIR)$(if $(PYTHONPATH),:$(PYTHONPATH),)

PC_RUN = $(PRE_COMMIT_BIN) run --all-files

.PHONY: repo-setup repo-validate repo-check repo-test \
	deps install-hooks doctor bootstrap ensure-toolchain \
	fmt hooks ensure-clean typecheck yaml-test compile manifest-check \
	check-full ci push \
	pre-commit lint gate

# --- Core Repository Execution V2 phases (make-v1 ABI) ----------------------

repo-setup: deps ## Create .venv and install the CI toolchain + pre-commit (= deps)

repo-validate: manifest-check ## Governance JSON, action pins, yamllint, MANIFEST.md currency
	$(PYTHON) lint/check_governance_json.py
	$(PYTHON) lint/check_action_pins.py
	$(PRE_COMMIT_BIN) run yamllint --all-files

repo-check: ## Non-mutating static gate: ruff check, ruff format --check, mypy l9_ci
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m mypy l9_ci

repo-test: ## pytest (PYTHONPATH=.)
	$(PYTHON) -m pytest -q $(PYTEST_ARGS)

# --- Bootstrap --------------------------------------------------------------

deps: ## Create .venv (if needed) and install CI toolchain + pre-commit
	@if [ ! -x "$(VENV_PYTHON)" ]; then \
	  python3 -m venv "$(VENV)"; \
	fi
	@# A venv created without pip (for example by `uv venv`) is repaired, not replaced.
	@"$(VENV_PYTHON)" -m pip --version >/dev/null 2>&1 || "$(VENV_PYTHON)" -m ensurepip --upgrade
	"$(VENV_PYTHON)" -m pip install -U pip
	"$(VENV_PYTHON)" -m pip install -r requirements-ci.txt pre-commit

install-hooks: ## Install git pre-commit and pre-push hooks (fail-closed push)
	$(PRE_COMMIT_BIN) install --hook-type pre-commit --hook-type pre-push

doctor: ## Verify gate tooling is present
	@ok=1; \
	echo "PYTHON=$(PYTHON)"; \
	if ! command -v "$(PYTHON)" >/dev/null 2>&1 && [ ! -x "$(PYTHON)" ]; then \
	  echo "missing: python ($(PYTHON))"; ok=0; \
	else \
	  "$(PYTHON)" --version; \
	fi; \
	if ! command -v "$(PRE_COMMIT_BIN)" >/dev/null 2>&1 && [ ! -x "$(PRE_COMMIT_BIN)" ]; then \
	  echo "missing: pre-commit (run: make deps)"; ok=0; \
	else \
	  "$(PRE_COMMIT_BIN)" --version; \
	fi; \
	if ! command -v git >/dev/null 2>&1; then \
	  echo "missing: git"; ok=0; \
	fi; \
	if ! "$(PYTHON)" -c 'import mypy, pytest' >/dev/null 2>&1; then \
	  echo "missing: mypy/pytest (run: make deps)"; ok=0; \
	fi; \
	hook_dir="$$(git rev-parse --git-path hooks 2>/dev/null || true)"; \
	if [ -n "$$hook_dir" ]; then \
	  if [ ! -x "$$hook_dir/pre-commit" ] || [ ! -x "$$hook_dir/pre-push" ]; then \
	    echo "git hooks incomplete — run: make install-hooks"; ok=0; \
	  else \
	    echo "git hooks: pre-commit + pre-push installed"; \
	  fi; \
	fi; \
	if [ "$$ok" -ne 1 ]; then exit 1; fi; \
	echo "doctor: ok"

bootstrap: deps install-hooks doctor ## One-shot onboarding

# Auto-run by check-full/push (and raw git push → pre-push → make check-full).
# If .venv/toolchain/hooks are missing, provision them; otherwise no-op.
ensure-toolchain: ## deps + hooks when missing (idempotent)
ifeq ($(origin PYTHON),command line)
	@if ! "$(PYTHON)" -c 'import mypy, pytest' >/dev/null 2>&1; then \
	  echo "PYTHON=$(PYTHON) missing mypy/pytest — install CI toolchain or omit PYTHON= to use .venv via make deps"; \
	  exit 1; \
	fi
else
	@if [ ! -x "$(VENV_PYTHON)" ] || ! "$(VENV_PYTHON)" -c 'import mypy, pytest' >/dev/null 2>&1; then \
	  echo "ensure-toolchain: provisioning .venv (make deps)"; \
	  $(MAKE) deps; \
	fi
endif
	@hook_dir="$$(git rev-parse --git-path hooks 2>/dev/null || true)"; \
	if [ -n "$$hook_dir" ] && { [ ! -x "$$hook_dir/pre-commit" ] || [ ! -x "$$hook_dir/pre-push" ]; }; then \
	  echo "ensure-toolchain: installing git hooks (make install-hooks)"; \
	  $(MAKE) install-hooks; \
	fi

# --- Mutate (intentional) ---------------------------------------------------

fmt: ensure-toolchain ## Run pre-commit suite (may autofix; commit results)
	$(PC_RUN)

# --- Verify -----------------------------------------------------------------

hooks: ensure-toolchain ## Run .pre-commit-config.yaml over all files
	$(PC_RUN)

ensure-clean: ## Fail if the working tree is dirty
	@if ! git diff --quiet || ! git diff --cached --quiet; then \
	  echo "working tree dirty after hooks — commit fixes, then re-run"; \
	  git status --short; \
	  exit 1; \
	fi

typecheck: ## mypy l9_ci
	$(PYTHON) -m mypy l9_ci

yaml-test: ## Fast yaml-governance pytest slice
	$(PYTHON) -m pytest -q tests/yaml $(PYTEST_ARGS)

compile: ## Byte-compile Python surfaces
	$(PYTHON) -m compileall -q l9_ci tests lint

# Same generator invocation as ci.yml's "Tracked manifest must be current", but
# written to a scratch file (the generator requires a path inside the
# repository) and compared, so a stale MANIFEST.md fails without being rewritten.
manifest-check: ## Fail if tracked MANIFEST.md is not current (non-mutating)
	@scratch="$$(mktemp "$(CURDIR)/.manifest-check.XXXXXX")"; \
	trap 'rm -f -- "$$scratch"' EXIT; \
	$(PYTHON) -m l9_ci manifest generate --repository-root . \
	  --output "$$(basename "$$scratch")" --tracked-only \
	  --exclude-dir memory-bank >/dev/null; \
	if ! diff -u MANIFEST.md "$$scratch"; then \
	  echo "MANIFEST.md is stale — regenerate: PYTHONPATH=\"\$$PWD\" python -m l9_ci manifest generate --repository-root . --output MANIFEST.md --tracked-only --exclude-dir memory-bank"; \
	  exit 1; \
	fi; \
	echo "MANIFEST.md: current"

# --- Compose / ship ---------------------------------------------------------

check-full: ensure-toolchain hooks ensure-clean typecheck repo-test ## Full local gate (hooks + mypy + pytest); the pre-V2 `make check`

ci: check-full compile ## Local CI-shaped gate

push: check-full ## Full gate then git push (pre-push hook skips re-entry)
	L9_MAKE_PUSH=1 git push $(PUSH_ARGS)

# Aliases (zero logic — agents/humans land on the SSOT path)
pre-commit: hooks ## Alias for hooks
lint: hooks ## Alias for hooks
gate: check-full ## Alias for check-full
