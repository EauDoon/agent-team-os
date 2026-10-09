PYTHON ?= python
PKG_VERSION := $(shell $(PYTHON) scripts/version.py)
PKG_ZIP := dist/agent-team-$(PKG_VERSION).zip

.PHONY: install test lint validate package clean evals ci

install:
	@$(PYTHON) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" \
		|| (echo 'Python 3.11 or later is required' >&2; exit 1)

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) scripts/validate.py

# Aggregate name for the contract check. The recipe already lives in `lint`;
# repeating it here emitted two identical reports for every `make validate`.
validate: lint

# Same order as CI: contract checks, regression tests, rubric cases, then the
# package build and its verification against source.
package: validate test evals
	$(PYTHON) scripts/package.py --output dist
	$(PYTHON) scripts/verify_package.py $(PKG_ZIP)

ci: package

clean:
	rm -rf dist

evals:
	$(PYTHON) evals/runner.py