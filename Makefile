.PHONY: all fmt fmt-fix lint types test build coverage audit mutate

all: fmt lint types coverage build

fmt:
	uv run --locked ruff format --check .

fmt-fix:
	uv run --locked ruff format .

lint:
	uv run --locked ruff check .

types:
	uv run --locked mypy src/stockchartsalerts
	uv run --locked pyright

test:
	uv run --locked pytest

coverage:
	uv run --locked pytest --cov=stockchartsalerts --cov-branch --cov-report=term-missing:skip-covered --cov-report=xml:coverage.xml

build:
	uv build

audit:
	uv run --locked pip-audit

mutate:
	uv run --locked mutmut run
