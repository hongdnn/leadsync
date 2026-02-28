# Demo FastAPI Backend

This folder is a small backend project used to demo PR auto-description.

## Files
- `app/users.py`
- `app/user_service.py`
- `tests/test_users.py`

## Run tests
```bash
source .venv/bin/activate
pytest demo/fastapi_backend/tests/test_users.py -q
```

## Run app
```bash
source .venv/bin/activate
uvicorn demo.fastapi_backend.app.main:app --reload --port 8010
```
