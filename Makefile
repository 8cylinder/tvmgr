SHELL := bash

.DEFAULT_GOAL := help
.PHONY: help check-cc sync fmt fmt-check lint lint-check type test docs docs-serve man check ci build install install-completions install-man uninstall upgrade clean

# pysmbc is a C extension. Prefer clang when it is installed, otherwise use
# gcc. Override the choice with `make SMBC_CC=gcc sync`.
SMBC_CC ?= $(shell command -v clang >/dev/null 2>&1 && echo clang || echo gcc)
export CC := $(SMBC_CC)

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-cc:  ## Verify that the selected C compiler exists
	@command -v "$(SMBC_CC)" >/dev/null 2>&1 || { echo "error: $(SMBC_CC) not found; install clang or gcc" >&2; exit 1; }

sync: check-cc  ## Install or update dependencies
	uv sync --all-groups

fmt:  ## Format code
	uv run ruff format .

fmt-check:  ## Check formatting without changing files
	uv run ruff format --check .

lint:  ## Lint and apply safe fixes
	uv run ruff check --fix .

lint-check:  ## Lint without changing files
	uv run ruff check .

type:  ## Type-check the project
	uv run ty check

test:  ## Run tests
	uv run pytest

docs:  ## Build HTML documentation
	uv run sphinx-build -W -b html docs docs/_build/html

docs-serve:  ## Serve documentation with live reload
	uv run sphinx-autobuild docs docs/_build/html

man:  ## Build the man page
	uv run sphinx-build -W -b man docs docs/_build/man

check: fmt-check lint-check type test docs  ## Run all checks without changing files

ci: check-cc  ## Install locked dependencies and run all checks
	uv sync --locked --all-groups
	$(MAKE) check

build:  ## Build the wheel and sdist
	uv build

install: check-cc  ## Install the app, bash completions, and man page
	uv tool install --editable --force .
	$(MAKE) install-completions install-man

install-completions:  ## Generate and install bash completions
	uv run tvmgr --completions

MANPAGE := docs/_build/man/tvmgr.1
MANDIR ?= $(if $(XDG_DATA_HOME),$(XDG_DATA_HOME),$(HOME)/.local/share)/man/man1

install-man: man  ## Install the man page
	mkdir -p "$(MANDIR)"
	install -m 644 "$(MANPAGE)" "$(MANDIR)/tvmgr.1"

uninstall:  ## Remove the installed tool
	uv tool uninstall tvmgr

upgrade: check-cc  ## Upgrade dependencies and the lockfile
	uv sync --upgrade --all-groups

clean:  ## Remove build and test artifacts
	rm -rf build dist docs/_build .pytest_cache .ruff_cache .ty_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
