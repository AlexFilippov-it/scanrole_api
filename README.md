# ScanRole API

Read-only JSON API for Role Explorer data. Auth is via Bearer token validated against WordPress introspection.

## Requirements
- Python 3.10+
- MySQL access to Role Explorer data table

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

Update `.env` values:
- `WP_INTROSPECT_URL` (e.g. `https://scanrole.com/wp-json/scanrole/v1/introspect`)
- `WP_INTROSPECT_SECRET`
- `DB_*` connection
- `ROLE_TABLE` (default `jobspy_normalized_jobs`)

## Run
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## External access
Provide your external API base URL to users (for example `https://scanrole.com/api/v1`). They need to:
1) Log in to WordPress and create a token in **Add API Token**.
2) Call the API with the Bearer token.

Example:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://scanrole.com/api/v1/role-explorer?period_days=30&country=United%20States&page=1&page_size=25"
```

## Deploy behind https://scanrole.com/api/v1 (reverse proxy)
This setup uses a local Uvicorn instance bound to `127.0.0.1:8001` and a web-server
proxy from `/api/v1` on the main domain.

1) Create `.env` with real values (see `.env.example`).
2) Start the service (systemd suggested). Template unit is in `deploy/scanrole-api.service`.
3) Add the proxy snippet from `deploy/nginx-scanrole-api.conf` to the server block for `scanrole.com`
   using FastPanel control panel (do not edit nginx configs manually).

## Auth flow
1. User logs into WordPress and generates a token in the Profile page.
2. Client calls API with:
   ```
   Authorization: Bearer <token>
   ```
3. API calls WordPress `POST /wp-json/scanrole/v1/introspect` to validate.

## Endpoints
- `GET /api/v1/role-explorer`
- `GET /api/v1/meta/periods`
- `GET /api/v1/meta/countries`
- `GET /api/v1/meta/states?country=United%20States`
- `GET /api/v1/meta/roles`
- `GET /api/v1/health`

### Example
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/role-explorer?period_days=30&country=United%20States&page=1&page_size=25"
```

## Error format
```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or expired token"
  }
}
```

## CI
GitHub Actions runs `ruff` and `pytest`.
