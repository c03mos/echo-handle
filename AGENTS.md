# Repository Guidelines

## Project Structure & Module Organization
This repository is currently minimal. The main project note is `handle.md`, which describes a FastAPI + SQLite processing service for the Echo system. Media resources are expected in a sibling `Data/` directory, and task orchestration comes from a sibling `Arrangement/` Spring Boot service.

When adding code, keep the layout simple and predictable:
- `app/` — FastAPI application code, routers, services, and database access
- `tests/` — automated tests mirroring the `app/` package structure
- `scripts/` — local maintenance or import/export helpers
- `.idea/` — editor metadata; do not rely on it for project behavior

## Build, Test, and Development Commands
No build or test automation is checked in yet. For new Python code, use standard FastAPI workflows:
- `python -m venv .venv` — create a local virtual environment
- `.\.venv\Scripts\Activate.ps1` — activate it in PowerShell
- `pip install fastapi uvicorn pytest` — install core runtime and test tools
- `uvicorn app.main:app --reload` — run the API locally with auto-reload
- `pytest` — run the test suite once tests are added

## Coding Style & Naming Conventions
Use 4-space indentation and follow PEP 8 for Python modules. Prefer clear, small modules over large mixed-purpose files. Use:
- `snake_case` for files, functions, and variables
- `PascalCase` for classes and Pydantic models
- lowercase route modules such as `app/routes/media_tasks.py`

Format with `black` and sort imports with `isort` if you add those tools.

## Testing Guidelines
Use `pytest` for all new tests. Name files `test_*.py` and keep test names behavior-focused, such as `test_rejects_missing_media_file`. Mirror production paths where practical, for example `tests/services/test_processor.py` for `app/services/processor.py`.

Cover API success paths, validation failures, and SQLite-backed persistence logic. Prefer temporary databases or fixtures over shared local state.

## Commit & Pull Request Guidelines
Git history is not accessible from this workspace, so no repository-specific commit pattern could be verified. Use short, imperative commit messages such as `Add media task endpoint` or `Fix SQLite session cleanup`.

For pull requests, include:
- a brief summary of the change
- linked issue or task ID, if available
- local test evidence (`pytest`, manual API check)
- request/response examples for API changes

## Security & Configuration Tips
Do not commit SQLite database files, media payloads, or absolute paths to sibling services. Keep environment-specific settings in local configuration files or environment variables, and document any required paths to `Data/` or `Arrangement/` in the PR description.
