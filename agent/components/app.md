# Component: app

## Metadata
- **Name**: app
- **Path**: `app/`
- **Type**: Service
- **Stack**: python
- **Framework**: flask
- **Language**: python

## Context
- **Source Root**: `app/`
- **Test Root**: `tests/`
- **Config**: `app/config.py`
- **Entrypoint**: `run.py` (via `flask run` or `gunicorn`)

## Commands
- **Run**: `flask run`
- **Test**: `pytest`
- **Lint**: `flake8 app/`
- **Format**: `black app/`
