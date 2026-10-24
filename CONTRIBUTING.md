# Contributing

Keep contributions scoped to the current phase or clearly document an agreed scope change. Use system Python in a virtual environment. Never commit `.env`, tokens, private logs, production security events, or database files.

Before submitting:

```bash
.venv/bin/pytest -c backend/pyproject.toml backend/tests -q
.venv/bin/ruff check backend scripts
.venv/bin/python scripts/check_offline.py
npm run build --prefix frontend
```

Add regression tests for changed validation, conversion, or detection behavior. Unsupported constructs must fail explicitly. Do not add mocked successes to live integration paths, claim ATT&CK coverage from one fixture, or change Splunk TLS defaults. Use sanitized or synthetic fixtures only. Never execute event command lines as part of testing.

Schema changes require Alembic migrations. Rule evidence must remain linked to an immutable YAML version and dataset snapshot. Runtime credentials belong in environment variables. Keep documentation aligned with implemented behavior. CI/CD and automated dependency scanning are planned for Phase 4.
