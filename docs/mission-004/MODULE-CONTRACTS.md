# Module contracts

`dh.observation/2`: id, source_id, key, kind, decimal-string value or text, unit, origin, observed_at, collected_at, issue_at, valid_at, raw, raw_hash, metadata, quality. Only normalization assigns provenance. Raw fields cannot promote imported evidence into observed or verified facts. Observation IDs depend on source, original content and mapping, not acquisition time. UPDATE and DELETE triggers protect the ledger.

`dh.source/1`: id, name, adapter, location, approved, enabled, interval (60–86400 seconds), mapping, default kind/unit/origin and reader options. Source IDs are bounded identifiers. Supported adapters: upload, file, HTTP API, read-only SQLite, Football Universe, legacy SCRAPP. No credentials may be embedded in recorded source URLs. Sources remain independently configurable.

`dh.task/1`: id, state (QUEUED, RUNNING, COMPLETE, FAILED, BLOCKED, INTERRUPTED, CANCELLED), created_at, updated_at, progress, immutable staged-file reference/source snapshot, result. A source cannot have competing active tasks. Cancellation before atomic commit rolls back the complete batch. A receipt and observations commit together; replay of a committed task returns that receipt.

`dh.acquisition-receipt/1`: task/import identity, source_id, method, content_hash, dataset_version when known, acquired_at, mapping, validation count, insertion/duplicate/conflict counts and committed_at. Missing provider versions remain null.

`dh.analysis/1`: algorithm/version, configuration, calculated_at, dataset_fingerprint, input IDs and values, source/series/unit/provenance scope, output and limitations. Derived values live in an independent analyses table. Correlation requires unique exact known observation times. Prediction evaluation does not establish prediction chronology.

The HTTP API is same-origin and loopback-only. GET status, observations, analyses, tasks, backups, sentiment and odds expose bounded data. JSON POST endpoints configure sources, import, cancel/resume, analyze, backup, configure/explain local AI, revoke sessions and shut down. Unknown inputs are rejected. Native restore runs only after the candidate stops and retains a pre-restore backup.

Read-only football schema 1 is validated by its `dragonhydra.football-universe` owner marker. Canonical historical matches and Bet365 pre-closing 1X2 prices are imported with retained original identifiers and original odds source hash/URL. No arbitrary SQL is executed. CORE mathematics is reused from preserved owned modules. SQL requires an explicit RELEASED guard before an injected scoped connector can run. No SQL schema changes happen automatically.
