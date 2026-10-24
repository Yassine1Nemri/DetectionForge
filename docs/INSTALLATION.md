# Installation

## Requirements

Use Linux, system Python 3.11–3.14 (verified here with 3.14), Node.js >=20.19 or >=22.12, npm, and Docker Compose for PostgreSQL deployment. Do not use Python or PostgreSQL executables bundled with Splunk. Dependency pins were resolved and tested on Python 3.14; the Docker image uses that interpreter.

## Native development

From the repository root:

```bash
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cp .env.example .env
.venv/bin/alembic -c backend/alembic.ini upgrade head
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

The default database is `detectionforge.db` in the working directory. Keep launching native commands from the root. The service intentionally does not create tables at startup: run migrations first.

In another terminal:

```bash
npm ci --prefix frontend
npm run dev --prefix frontend
```

Visit http://127.0.0.1:5173 . Vite proxies `/api` to port 8000. No credentials belong in the browser configuration.

## PostgreSQL deployment

1. Copy `.env.example` to `.env` and choose `POSTGRES_PASSWORD`. Protect the file (`chmod 600 .env`). Do not commit it.
2. Run `docker compose up --build -d`.
3. Visit http://127.0.0.1:8080 . PostgreSQL is bound to loopback port 5433; the backend has no host port. nginx serves the built frontend and proxies `/api`.
4. `docker compose logs backend` diagnoses migration/startup failures. Avoid sharing logs containing private configuration.

The Compose backend receives `PGPASSWORD` separately from its database URL; punctuation in that password needs no URL encoding. It always uses PostgreSQL, regardless of the native `DATABASE_URL` in `.env`. PostgreSQL data persists in `postgres_data`. `docker compose down` stops containers and preserves the volume. Removing the volume destroys stored versions and results.

For native backend development with the Compose database, run `docker compose up -d db`, then set `DATABASE_URL` to a `postgresql+psycopg://` URL using your matching user, URL-encoded password, and port 5433. Alternatively omit the URL password and set `PGPASSWORD` in the backend process environment. Run migrations and start the native backend as above.

Compose runtime memory caps: PostgreSQL 384 MB, API 384 MB, frontend 128 MB. Build tools temporarily need additional memory. There is no queue, worker, or extra Splunk deployment.

## Operational boundary

This MVP is a trusted local development application without authentication. Bind it to loopback. Network deployment requires authentication, authorization, TLS termination, and an access-control review. Only validated imports are persisted. No user accounts, telemetry export, or outbound Splunk requests exist in Phase 1.

## Configuration

- `DATABASE_URL`: SQLAlchemy connection URL for native operation.
- `CORS_ORIGINS`: JSON array; native Vite origins by default, no cross-origin access in Compose.
- `SPLUNK_FIELD_MAPPINGS`: JSON object of canonical Sigma fields to your extracted field names; default EventID → EventCode. Values must be simple identifiers. Keep mappings aligned with the deployment; generated queries are previews.

Never use Splunk's embedded libraries for this app, and never disable TLS as a workaround when implementing Phase 2.
