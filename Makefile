.PHONY: check sync
sync:
	uv sync
check: sync
	@set -e; for f in tests/test_*.py; do echo "== $$f"; uv run python $$f; done
