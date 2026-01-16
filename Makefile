.PHONY: help install dev test test-cov test-watch migrate upgrade lint format

help:
	@echo "Available commands:"
	@echo "  make install     - Install dependencies"
	@echo "  make dev         - Start development server"
	@echo "  make celery      - Start Celery worker"
	@echo "  make migrate     - Create new migration"
	@echo "  make upgrade     - Run database migrations"
	@echo "  make test        - Run tests"
	@echo "  make test-cov    - Run tests with coverage report"
	@echo "  make test-watch  - Run tests in watch mode"
	@echo "  make lint        - Run linter"
	@echo "  make format      - Format code"

install:
	pip install -r requirements.txt

dev:
	python run.py

celery:
	celery -A app.services.queue.tasks worker --loglevel=info

migrate:
	alembic revision --autogenerate -m "$(msg)"

upgrade:
	alembic upgrade head

test:
	pytest

test-cov:
	pytest --cov=app --cov-report=html --cov-report=term-missing

test-watch:
	pytest-watch

test-fast:
	pytest -n auto

lint:
	ruff check .

format:
	black .
	ruff check --fix .

