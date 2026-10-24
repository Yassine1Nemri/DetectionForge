# Phase 1 verification evidence

Verified in this workspace on 2026-10-24 (Africa/Tunis).

| Check | Actual result |
| --- | --- |
| Backend suite | **39 passed, 0 failed** |
| pySigma / Splunk compatibility | pySigma 1.5.1 and Splunk backend 2.1.0 imported and converted the sample with source and field-mapping assertions |
| Offline repository scenario checks | **2 passed**: positive exact matches and benign no-match fixture |
| Ruff | Passed for backend and scripts |
| Prettier | Frontend source formatting check passed |
| Python dependency consistency | `pip check`: no broken requirements |
| Frontend | TypeScript compilation and Vite production build passed |
| npm dependency audit during install / container build | 0 reported vulnerabilities in the resolved frontend graph |
| Docker Compose | PostgreSQL 17, backend, and frontend built and started; DB/API healthchecks healthy |
| Migrations | Actual PostgreSQL schema initialized by Alembic; SQLite migration upgrade/downgrade/upgrade matches ORM metadata in tests |
| Browser workflow | Imported sample → validated → generated real SPL → saved → selected positive dataset → executed and inspected report → selected benign dataset → executed and inspected report |
| Persistence | Rebuilt/recreated API and frontend containers; saved rule and both actual test runs remained visible after page reload |

## Browser test results

The positive dataset matched exactly `ps-encoded` and `ps-short-switch`; the cmd.exe control did not match. TP=2, FP=0, TN=1, FN=0; precision=1 and recall=1 for these fixtures.

The benign dataset matched no events. TP=0, FP=0, TN=2, FN=0; precision and recall were correctly undefined (JSON null, displayed as an em dash).

Both runs were executed from the UI against the PostgreSQL-backed service. Their evidence is stored in the local database. There is no automatic seed or fabricated run history. The standalone offline report script separately generates `reports/offline-report.json` from actual execution.

API regression tests also prove that deliberate broadening produces stored false-positive FAIL results, rule revisions retain earlier source evidence, stale updates return 409, disabled rules cannot execute, unsupported constructs reject rather than pass, report downloads retain source YAML and datasets, and oversized/unsafe inputs fail.

## Limitations of verification

The API tests use isolated SQLite databases; the browser workflow and persistence check exercised actual PostgreSQL. No real Splunk search or ingestion was performed, and no ATT&CK catalog validation or coverage claim was tested. Python vulnerability auditing and automated CI dependency scanning are deferred; Python `pip check` verifies dependency consistency only. The test stack emits one Starlette deprecation warning for the HTTPX test transport, with no failures. No load test, authentication test, or claim of production readiness is made.

The sandbox blocks the synchronous test client's thread event loop. API tests were run successfully outside that sandbox; the application itself also ran successfully in Docker.

## Screenshot

This is a capture of the actual running application after those two fixture tests, not a mockup.

![Phase 1 dashboard after real offline fixture runs](screenshots/phase1-dashboard.png)
