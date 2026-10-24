# Architecture and decisions

Phase 1 is a single FastAPI service, PostgreSQL database, and React/TypeScript client. Docker Compose runs those components only; it never starts Splunk. No queue, Redis, Kubernetes, or AI component is required. Offline operations run synchronously against bounded inputs.

## Data model

- `rules`: Sigma UUID, current title, severity, log source, tags, enabled state, current version, modification time.
- `rule_versions`: immutable YAML snapshots, version number, creation time; unique per rule/version.
- `test_runs`: UUID, rule/version, dataset snapshot, mode, verdict, matched and expected event IDs, metrics, duration, creation time. Runs retain their source YAML through the referenced immutable version.

Migrations use Alembic. PostgreSQL is the deployment database. SQLite is an explicit local/test option, with foreign keys enabled. Import validates before storing. Updates require the expected current version to prevent lost edits. Reports are computed by the backend and persisted; the UI does not invent counts or history. No example rules are automatically inserted into the database.

## Validation and conversion

Use safe, bounded YAML loading with duplicate-key and alias rejection, then pySigma parsing and platform metadata requirements. pySigma is the authority for Sigma parsing. SplunkBackend performs conversion. Phase 1 accepts a single standard rule, not correlation collections. Conversion requires a Windows process-creation log source. A trusted programmatic pipeline adds Sysmon EventID 1 and its source, maps EventID to EventCode, then applies environment-configured field mappings. Unknown source profiles fail explicitly. Generated SPL is a preview only and is never executed in Phase 1.

Compatibility gate: upstream Splunk backend 2.1.0 declares `pysigma ^1` and Python >=3.10. Resolve a stable 1.x release, pin exact versions, and verify actual imports and conversions in tests. Sources: https://github.com/SigmaHQ/pySigma-backend-splunk/blob/main/pyproject.toml and https://sigmahq.io/docs/digging-deeper/pipelines.html .

## Event schema and offline methodology

A dataset is JSON with a stable ID, rule UUID, category (`malicious` or `benign`), ATT&CK technique, declared log source, events, expected event IDs, and expected detection boolean. Each event has a unique ID, timezone-aware timestamp, and scalar canonical Sigma fields. Expected IDs must exist, agree with the boolean, and match the category. No event commands are executed.

Offline testing evaluates a deliberately limited, documented Sigma subset against canonical fields: named selections with exact, contains, startswith, endswith, optional all; list values are OR unless all; condition trees support AND/OR/NOT and selection quantifiers through the pySigma AST. String matching is case-insensitive. Unsupported modifiers, wildcard values, types, or conditions reject the entire test before evaluating events. Log sources must agree. This is fixture evaluation, not an SPL interpreter or a Splunk result.

Compare exact event ID sets, report missing/unexpected matches, TP/FP/TN/FN, precision and recall (null when undefined). Positive truth labels are the expected IDs, independent of actual matches. Verdict requires both exact sets and the expected boolean. Report mode is always `offline`; each run has a UUID and uses an in-memory isolated dataset. Phase 2 will use a dedicated test index AND a server-generated run ID in every search. Phase 1 never connects to production indexes.

## Risks and boundaries

- Offline semantics can differ from Splunk extraction/case rules; passing fixtures never proves live SIEM efficacy.
- Synthetic command lines exercise selected patterns only; they do not establish complete ATT&CK coverage.
- The source/field pipeline must match actual Sysmon onboarding. XML sources and CIM need separate verified profiles.
- Arbitrary Sigma constructs may parse but be unsupported offline. Fail closed; never convert unsupported results into a pass.
- YAML is untrusted: byte limits, no custom objects, aliases or duplicate keys; offline event limits.
- Phase 1 binds to loopback and has no authentication. Do not expose it to a network without authentication and access controls.
- PostgreSQL concurrency uses optimistic versioning and transactions. Test evidence belongs to its exact version; stale results are shown separately.
- ATT&CK tags are extracted; authoritative ATT&CK catalog validation and coverage are deferred to Phase 3.
