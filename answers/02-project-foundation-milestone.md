# Milestone: Project Foundation

## Plan

Replace the PyCharm template with a minimal FastAPI app, keep dependency management as light as possible (a plain `requirements.txt` using the existing `.venv` — no Poetry/uv), add a `.gitignore` covering venv/IDE/cache noise, and a README with the run command. No folders, no routers, no config system — just enough to prove the app boots and responds.

## Files created / modified

| File | Purpose |
|---|---|
| `main.py` | Replaced the PyCharm "Hi" template with a minimal FastAPI app exposing a single `GET /health` endpoint returning `{"status": "healthy"}`. This is the entire application for this milestone. |
| `requirements.txt` | Pinned direct dependencies: `fastapi==0.139.2`, `uvicorn[standard]==0.51.0`. Kept to a plain requirements file rather than Poetry/uv since no decision was made on tooling and this is the simplest option that works with the existing `.venv`. |
| `.gitignore` | Excludes `.venv/`, `__pycache__/`, `*.pyc`, `.idea/`, `.env` — none of these belong in version control. |
| `README.md` | Two-command run instructions (install deps, start server) plus the health-check URL. |

## Verified

Installed dependencies into the existing `.venv`, started the server with `uvicorn main:app`, and confirmed `GET /health` returns `200 OK` with `{"status":"healthy"}`.

## Run command

```
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn main:app --reload
```

Then visit `http://127.0.0.1:8000/health`.

## Note

`.idea/` files were already staged in git from before this milestone (added by PyCharm, never committed). They're now covered by `.gitignore`, but since they were already in the index, `.gitignore` won't automatically untrack them — running `git rm -r --cached .idea` would be needed to remove them from the staging area if desired. No git action was taken.
