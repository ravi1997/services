.PHONY: venv install test run celery fmt clean db-revision db-upgrade db-downgrade db-current

VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip
PYTEST=$(VENV)/bin/pytest

venv:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip

install: venv
	$(PIP) install -r requirements.txt

test:
	$(PYTEST) -q

run:
	$(PY) run.py

celery:
	$(VENV)/bin/celery -A app.celery worker --loglevel=info

clean:
	rm -rf $(VENV) *.pyc __pycache__ .pytest_cache sms.db instance logs/*.log

db-revision:
	$(VENV)/bin/alembic revision --autogenerate -m "auto"

db-upgrade:
	$(VENV)/bin/alembic upgrade head

db-downgrade:
	$(VENV)/bin/alembic downgrade -1

db-current:
	$(VENV)/bin/alembic current
