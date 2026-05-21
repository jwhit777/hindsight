PYTHON ?= python3

.PHONY: smoke test lint build clean install dev dev-live publish-test publish

smoke:
	@$(PYTHON) src/spike_run.py

test:
	@$(PYTHON) -m unittest discover -s src -p 'test_*.py' -v

lint:
	@$(PYTHON) -m ruff check src/

build:
	@$(PYTHON) -m build

clean:
	@rm -rf build/ dist/ *.egg-info src/*.egg-info .ruff_cache .mypy_cache
	@find . -type d -name '__pycache__' -exec rm -rf {} +

install:
	@$(PYTHON) -m pip install -e .

dev:
	@$(PYTHON) -m pip install -e '.[dev]'

# Live providers (anthropic + openai) are kept separate so contributors
# don't pull SDK dependencies they don't need.
dev-live:
	@$(PYTHON) -m pip install -e '.[dev,live]'

# Reserve / publish to test.pypi.org first. Requires a testpypi API token
# in $TWINE_PASSWORD (with TWINE_USERNAME=__token__).
publish-test: build
	@$(PYTHON) -m twine upload --repository testpypi dist/*

# Real PyPI publish. Requires a pypi.org API token (same env vars).
# Version in pyproject.toml is the one that ships; bump before invoking.
publish: build
	@$(PYTHON) -m twine upload dist/*
