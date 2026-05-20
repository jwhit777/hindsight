PYTHON ?= python3

.PHONY: smoke test lint build clean

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
