.PHONY: check check-frontend lock
check:
	uv run ruff check . && uv run ruff format --check . \
	  && uv run mypy src tests && uv run bandit -q -r src \
	  && uv run pip-audit && uv run pytest -q

check-frontend:
	cd frontend && npm audit --omit=dev --audit-level=high && npm run lint && npm run build \
	  && npx ng test --watch=false && npx playwright test

lock:
	uv export --frozen --no-dev --no-emit-project --format requirements-txt -o requirements.lock
