# Simple Social — FastAPI + Streamlit

A small demo social app built with FastAPI for the backend and Streamlit as a lightweight frontend. It uses ImageKit for media hosting and SQLite for local development.

Project layout

- `main.py` — tiny runner that launches the FastAPI app with Uvicorn.
- `app/` — core FastAPI application code (routes, database models, ImageKit wiring).
- `frontend.py` — Streamlit client used to interact with the API.
- `pyproject.toml` — project metadata and Python dependencies.
- `test.db` — local SQLite DB used for development (gitignored by default).

Requirements

- Python 3.12+
- The dependencies in `pyproject.toml` (install with pip).

Quick start (dev)

1. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies

```bash
pip install -U pip
pip install -e .
# OR if you prefer:
# pip install -r requirements.txt
```

3. Copy the example env and fill in secrets

```bash
cp .env.example .env
# Edit .env and provide IMAGEKIT_PRIVATE_KEY, IMAGEKIT_PUBLIC_KEY, IMAGEKIT_URL_ENDPOINT
```

4. Run the backend API

```bash
python main.py
# or directly:
# uvicorn app.app:app --reload --host 0.0.0.0 --port 8000
```

5. Run the Streamlit frontend in a separate terminal

```bash
streamlit run frontend.py
```

Notes

- Authentication: the project uses FastAPI Users (JWT). Use the register/login endpoints provided at `/auth` and `/auth/jwt/login`.
- Image uploads go to ImageKit. If you do not set ImageKit credentials the SDK fallback values will be used (they're placeholders in the repo) — set real keys in `.env` for production.
- Database: defaults to a local SQLite file `test.db` and will be created/updated automatically.
- CORS: the FastAPI app is configured to allow requests from `http://localhost:8501` (Streamlit default). Adjust as needed in `app/app.py`.
