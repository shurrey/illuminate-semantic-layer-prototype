.PHONY: setup data demo test format lint run-api clean

PY := python

setup:
	uv sync --extra dev

data:
	uv run $(PY) -m data.generate

demo:
	uv run semantic-layer demo

test:
	uv run pytest -q

lint:
	uv run ruff check semantic_layer tests data
	uv run ruff format --check semantic_layer tests data

format:
	uv run ruff format semantic_layer tests data

run-api:
	uv run uvicorn semantic_layer.api:app --reload --port 8000

clean:
	rm -rf .venv .ruff_cache .pytest_cache dist build *.egg-info
	rm -f data/seed.duckdb telemetry.db
