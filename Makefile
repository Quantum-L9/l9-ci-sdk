# l9-ci-sdk local gate — orchestrates SSOTs; does not restate tool flags.
# Authority: .pre-commit-config.yaml (hooks) + requirements-ci.txt (toolchain).
# Ship path: make push  (also enforced by the git pre-push hook).

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

VENV        := $(CURDIR)/.venv
VENV_PYTHON := $(VENV)/bin/python
# Prefer repo venv when present; override with PYTHON=/path/to/python.
ifeq ($(origin PYTHON),command line)
  PYTHON_RESOLVED := $(PYTHON)
else ifneq ($(wildcard $(VENV_PYTHON)),)
  PYTHON_RESOLVED := $(VENV_PYTHON)
else
  PYTHON_RESOLVED := python3
endif
PYTHON      := $(PYTHON_RESOLVED)
# Do not name this PRE_COMMIT — that env var is reserved/collides under hook runs.
PRE_COMMIT_BIN ?= $(if $(wildcard $(VENV)/bin/pre-commit),$(VENV)/bin/pre-commit,pre-commit)
PYTEST_ARGS ?=
PUSH_ARGS   ?=

export PYTHONPATH := $(CURDIR)$(if $(PYTHONPATH),:$(PYTHONPATH),)

PC_RUN := $(PRE_COMMIT_BIN) run --all-files

.DEFAULT_GOAL := help

.PHONY: help deps install-hooks doctor bootstrap \
	fmt hooks ensure-clean typecheck test yaml-test compile \
	check ci push \
	pre-commit lint gate

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "; printf "Targets:\n"} \
		/^[a-zA-Z0-9_-]+:.*?## / {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- Bootstrap --------------------------------------------------------------

deps: ## Create .venv (if needed) and install CI toolchain + pre-commit
	@if [ ! -x "$(VENV_PYTHON)" ]; then \
	  python3 -m venv "$(VENV)"; \
	fi
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

# --- Mutate (intentional) ---------------------------------------------------

fmt: ## Run pre-commit suite (may autofix; commit results)
	$(PC_RUN)

# --- Verify -----------------------------------------------------------------

hooks: ## Run .pre-commit-config.yaml over all files
	$(PC_RUN)

ensure-clean: ## Fail if the working tree is dirty
	@if ! git diff --quiet || ! git diff --cached --quiet; then \
	  echo "working tree dirty after hooks — commit fixes, then re-run"; \
	  git status --short; \
	  exit 1; \
	fi

typecheck: ## mypy l9_ci
	$(PYTHON) -m mypy l9_ci

test: ## pytest (PYTHONPATH=.)
	$(PYTHON) -m pytest -q $(PYTEST_ARGS)

yaml-test: ## Fast yaml-governance pytest slice
	$(PYTHON) -m pytest -q tests/yaml $(PYTEST_ARGS)

compile: ## Byte-compile Python surfaces
	$(PYTHON) -m compileall -q l9_ci tests lint

# --- Compose / ship ---------------------------------------------------------

check: hooks ensure-clean typecheck test ## Full local gate (hooks + mypy + pytest)

ci: check compile ## Local CI-shaped gate

push: check ## Full gate then git push (pre-push hook skips re-entry)
	L9_MAKE_PUSH=1 git push $(PUSH_ARGS)

# Aliases (zero logic — agents/humans land on the SSOT path)
pre-commit: hooks ## Alias for hooks
lint: hooks ## Alias for hooks
gate: check ## Alias for check
