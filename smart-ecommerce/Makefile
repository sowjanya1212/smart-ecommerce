.PHONY: setup migrate seed admin api test
PY ?= python3

setup:            ## create venv + install both apps' dependencies
	$(PY) -m venv .venv
	.venv/bin/pip install -r admin_panel/requirements.txt -r api/requirements.txt
	test -f .env || cp .env.example .env

migrate:          ## create/upgrade the database schema (Django owns the schema)
	cd admin_panel && ../.venv/bin/python manage.py migrate

seed:             ## demo users, products and 30 days of orders
	cd admin_panel && ../.venv/bin/python manage.py seed_demo

admin:            ## Django admin panel on :8001
	cd admin_panel && ../.venv/bin/python manage.py runserver 8001

api:              ## FastAPI user panel + storefront on :8000
	cd api && ../.venv/bin/uvicorn app.main:app --reload --port 8000

test:
	cd api && ../.venv/bin/python -m pytest -q
