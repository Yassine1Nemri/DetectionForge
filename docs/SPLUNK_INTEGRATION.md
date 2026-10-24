# Splunk integration

## Implemented in Phase 1

DetectionForge converts Sigma to Splunk SPL using the maintained pySigma backend. It does not execute searches, authenticate, ingest events, or change the existing Splunk installation. No connection status in the UI claims successful integration.

The initial conversion profile adds `EventID: 1` and `source: WinEventLog:Microsoft-Windows-Sysmon/Operational`, then applies the deployment mapping (default EventID → EventCode). It assumes classic raw Windows Sysmon event extraction. Verify the exact source and field names in your existing deployment. XML WinEventLog source names and CIM require separate verified profiles; they are not covered by this preview.

`SPLUNK_FIELD_MAPPINGS` accepts a JSON field map in the backend environment. The frontend cannot submit arbitrary pipelines. Unknown source profiles fail, and backend conversion errors are surfaced. A preview is not scoped for live test execution and must not be used as the Phase 2 search wrapper.

## Phase 2 plan — not available yet

Reuse the existing Splunk Enterprise service. Configure its management API and HEC only when implementing this phase. Use environment-provided credentials, verified TLS, least privilege, and a dedicated test index distinct from production indexes. Do not grant access to all indexes or disable TLS verification by default.

The connector must handle authentication, permissions, request deadlines, search job polling/cancellation, partial responses, ingestion visibility, and field extraction. Every test event needs a server-created run ID plus fixture event ID. Every search must scope to BOTH the configured allowlisted test index and the run ID so unrelated production events cannot satisfy expected matches.

Required capabilities will be documented against the actual implementation and installed Splunk version: permission to search only the dedicated test index and an HEC token restricted to that index. Do not create a broad administrative service account for testing. Local integration tests or an explicitly authorized self-hosted runner will exercise the connector; public GitHub runners will perform offline checks only.

No Splunk credentials are requested or needed to run Phase 1.
