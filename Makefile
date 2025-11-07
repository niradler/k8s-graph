.PHONY: help install install-dev test test-cov lint format type-check check build clean
.PHONY: validate examples

help:
	@echo "k8s-graph Makefile"
	@echo ""
	@echo "Development:"
	@echo "  install      - Install package with uv"
	@echo "  install-dev  - Install with dev dependencies"
	@echo "  test         - Run pytest"
	@echo "  test-cov     - Run tests with coverage"
	@echo "  lint         - Run ruff linter"
	@echo "  format       - Format code with black"
	@echo "  type-check   - Run mypy type checking"
	@echo "  check        - Run all checks (format, lint, type-check, test)"
	@echo ""
	@echo "Validation & Use Cases:"
	@echo "  validate         - Run all use case scenarios"
	@echo "  validate-default - Build graph for default namespace"
	@echo "  validate-deploy  - Build graph from specific deployment"
	@echo "  examples         - Run example scripts"
	@echo ""
	@echo "Build & Clean:"
	@echo "  build        - Build distribution packages"
	@echo "  clean        - Remove build artifacts"

install:
	uv pip install -e .

install-dev:
	uv pip install -e ".[dev]"

test:
	uv run pytest -v

test-cov:
	uv run pytest -v --cov=k8s_graph --cov-report=term-missing --cov-report=html

lint:
	uv run ruff check k8s_graph tests examples

format:
	uv run black k8s_graph tests examples
	uv run ruff check --fix k8s_graph tests examples

type-check:
	uv run mypy k8s_graph

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

validate:
	@echo "🔍 Running all use cases..."
	uv run python scripts/use_cases.py --all-use-cases

validate-default:
	@echo "🔍 Building default namespace graph..."
	uv run python scripts/use_cases.py --namespace default

validate-deploy:
	@echo "🔍 Building graph from deployment..."
	uv run python scripts/use_cases.py --resource Deployment/crashloop-deploy-6444 --namespace default

examples:
	@echo "🚀 Running examples..."
	@for file in examples/*.py; do \
		echo "Running $$file..."; \
		uv run python $$file || true; \
	done
