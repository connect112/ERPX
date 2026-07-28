.PHONY: up down build logs migrate revision seed test test-api test-web lint fmt shell-api shell-web

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

migrate:
	docker compose exec api alembic upgrade head

revision:
	docker compose exec api alembic revision --autogenerate -m "$(m)"

seed:
	docker compose exec api python -m scripts.seed

test-api:
	docker compose exec api pytest -v --cov=app --cov=modules

test-web:
	docker compose exec web npm run test

test: test-api test-web

lint:
	docker compose exec api ruff check .
	docker compose exec web npm run lint

shell-api:
	docker compose exec api /bin/bash

shell-web:
	docker compose exec web /bin/sh

psql:
	docker compose exec postgres psql -U erpx -d erpx
