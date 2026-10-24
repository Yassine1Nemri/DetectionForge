# Implementation roadmap

1. **Phase 1:** bounded Sigma import/validation, immutable versions, Splunk preview, persisted offline PowerShell fixture tests, basic responsive UI, PostgreSQL migration, reproducible dependencies and focused tests. Acceptance: import sample from UI, inspect real generated SPL, run positive and negative fixtures, inspect/download genuine offline report.
2. **Phase 2:** existing Splunk connector with TLS verification, least-privilege credentials and allowlisted dedicated index; HEC ingestion and propagation polling; run-ID isolation; real search jobs, deadlines, cancellation, history, integration tests. Never fall back to offline mode.
3. **Phase 3:** authentication correlation (4625/time window/threshold) and scheduled-task scenarios; benign fixtures; pinned Enterprise ATT&CK catalog and reference validation; measured coverage states and reports.
4. **Phase 4:** GitHub Actions validation/conversion/offline checks, dependency scanning, separately enabled authorized self-hosted Splunk tests. Public CI never needs local Splunk access.
5. **Phase 5:** UI polish, real screenshots, demonstration evidence, packaging and release review. No release or external publication is automatic.

Dependencies: verify source profiles before live tests; implement correlation explicitly before brute force; ingest a versioned official catalog before claiming ATT&CK validity or coverage. Definition of done in the master brief spans later phases and is not achieved by Phase 1 alone.
