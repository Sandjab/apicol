.PHONY: install check format lint typecheck test test-integration clean

install:
	uv sync --all-extras

format:
	uv run ruff format src tests

lint:
	uv run ruff check src tests

typecheck:
	uv run mypy --strict src

test:
	uv run pytest -xvs --cov=src/apicol --cov-report=term-missing --cov-fail-under=95

test-integration:
	uv run pytest -xvs tests/integration -m integration

check:
	uv run ruff format --check src tests
	uv run ruff check src tests
	uv run mypy --strict src
	uv run pytest -xvs --cov=src/apicol --cov-fail-under=95

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
