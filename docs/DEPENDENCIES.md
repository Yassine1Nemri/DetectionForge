# Dependency choices

Versions were resolved on 2026-10-24. `backend/requirements.lock` pins the complete Python environment; `frontend/package-lock.json` locks the frontend graph. Use these files rather than re-resolving version ranges for a reproduction.

- Python 3.14: verified local runtime and Docker base. pySigma supports Python >=3.11. The project's code targets Python >=3.11, while this lock and deployment are tested on 3.14.
- pySigma **1.5.1** and Splunk backend **2.1.0**: upstream backend declares `pysigma ^1`. Actual parsing, source scoping, field mapping, and conversion are exercised by tests. Do not migrate pySigma across a major boundary without rerunning those checks. [Upstream compatibility declaration](https://github.com/SigmaHQ/pySigma-backend-splunk/blob/main/pyproject.toml).
- FastAPI **0.162.0**, Pydantic **2.14.1**, settings **2.16.1**: maintained typed API/schema stack; body limits and strict dataset validation are application responsibilities.
- SQLAlchemy **2.1.6**, Alembic **1.20.1**, psycopg **3.3.6**: synchronous persistence is sufficient for bounded local operations and avoids a second async database stack. PostgreSQL 17 provides a supported deployment target; SQLite simplifies isolated unit tests.
- PyYAML **6.0.3**: SafeLoader with application-level alias, duplicate-key, depth, node, and byte restrictions.
- pytest **9.1.1**, HTTPX **0.28.1**, Ruff **0.17.2**: verification tooling. The resolved Starlette emits a warning about its legacy HTTPX test transport; API tests pass. A future transport change should be deliberate and tested.
- React 19, TypeScript 5.9, Vite 7, Tailwind 4: a small maintained client stack compatible with the workstation's Node 20.20.2. The lockfile holds exact versions. Tailwind is integrated through the official Vite plugin; visual styles use the local stylesheet and no external fonts, assets, or CDNs.

Check dependencies periodically with `npm audit --prefix frontend` and `pip-audit -r backend/requirements.lock` in a separate tooling environment. Automated vulnerability scanning and CI policy are Phase 4 work. No claim is made that a successful build is a vulnerability audit. Container base tags receive maintenance updates and are not digest locked in this MVP.
