.PHONY: help install install-dev test test-cov lint format type-check check build clean

help:
	@echo "k8s-graph Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  install      - Install package with uv"
	@echo "  install-dev  - Install with dev dependencies"
	@echo "  test         - Run pytest"
	@echo "  test-cov     - Run tests with coverage"
	@echo "  lint         - Run ruff linter"
	@echo "  format       - Format code with black"
	@echo "  type-check   - Run mypy type checking"
	@echo "  check        - Run all checks (format, lint, type-check, test)"
	@echo "  build        - Build distribution packages"
	@echo "  clean        - Remove build artifacts"

install:
	uv pip install -e .

install-dev:
	uv pip install -e ".[dev]"

test:
	.venv/bin/pytest -v

test-cov:
	.venv/bin/pytest -v --cov=k8s_graph --cov-report=term-missing --cov-report=html

lint:
	.venv/bin/ruff check k8s_graph tests examples

format:
	.venv/bin/black k8s_graph tests examples
	.venv/bin/ruff check --fix k8s_graph tests examples

type-check:
	.venv/bin/mypy k8s_graph

check: format lint type-check test-cov

build: clean
	uv build

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

