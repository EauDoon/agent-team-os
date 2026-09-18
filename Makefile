PYTHON ?= python
PKG_VERSION := $(shell $(PYTHON) -c "import pathlib; print(pathlib.Path('VERSION').read_text(encoding='utf-8').strip())")
PKG_ZIP := dist/agent-team-$(PKG_VERSION).zip

.PHONY: install test lint validate package clean

install:
	@$(PYTHON) -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" \
		|| (echo 'Python 3.11 or later is required' >&2; exit 1)

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) scripts/validate.py

validate: lint
	$(PYTHON) scripts/validate.py

package: validate test
	$(PYTHON) scripts/package.py --output dist
	$(PYTHON) scripts/verify_package.py $(PKG_ZIP)

clean:
	rm -rf dist