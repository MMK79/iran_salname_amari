# make up | etl | load | test | lint | dashboard | etl-local
SOURCE_DIR ?= /Volumes/MigMig/Programming/Datasets/Statistical Yearbook/Keshvari
PG ?= postgresql://edu:edu@localhost:5433/edu
export SOURCE_DIR

up:            ## start Postgres 16 (data volume persisted)
	docker compose up -d db

etl:           ## full pipeline inside docker: convert .doc, extract, validate, load into Postgres
	docker compose --profile etl run --rm etl sh -c "scripts/convert_docs.sh 4 && uv run python -m etl.run extract && uv run python -m etl.run validate && uv run python -m etl.run load"

etl-local:     ## same pipeline on the host; loads Postgres if it is up, else DuckDB (data/out/edu.duckdb)
	scripts/convert_docs.sh 4
	uv run python -m etl.run extract
	uv run python -m etl.run validate
	@if docker compose ps db 2>/dev/null | grep -q healthy; then uv run python -m etl.run load --pg $(PG); \
	 else uv run python -m etl.run load --duckdb data/out/edu.duckdb; fi

load:          ## (re)load parquet outputs into Postgres
	uv run python -m etl.run load --pg $(PG)

test:
	uv run pytest -q

lint:
	uv run ruff check etl tests dashboard

dashboard:     ## Streamlit prototype on http://localhost:8501 (reads DuckDB or Postgres)
	uv run streamlit run dashboard/app.py

down:
	docker compose down
.PHONY: up etl etl-local load test lint dashboard down
