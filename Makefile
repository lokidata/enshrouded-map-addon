.PHONY: check lock
check:
	uv run ruff check . && uv run ruff format --check . \
	  && uv run mypy src tests && uv run bandit -q -r src \
	  && uv run pip-audit && uv run pytest -q

lock:
	uv export --frozen --no-dev --no-emit-project --format requirements-txt -o requirements.lock
