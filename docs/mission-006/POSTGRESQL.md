# PostgreSQL datastore — 0.2.0-beta.4 candidate

Open PostgreSQL Control Center. Configure the existing local server and an isolated `dragonhydra_` schema. Save separate read-only and application credentials through the protected credential controls, or reuse the authorized local Mission 001 profiles. Test Connection executes real PostgreSQL queries; service discovery alone never establishes connection success.

Initialize only an authorized owned schema. Migrate a preserved SQLite snapshot (blank path selects this workspace). The engine takes a coherent SQLite backup and verifies every original observation ID and UTF-8 payload. Then select **Use verified PostgreSQL as primary**. CSV and football acquisitions, history, numerical analysis and AI evidence queries now use PostgreSQL. Local SQLite continues to hold application settings, tasks and sessions. Select **Use preserved SQLite offline datastore** explicitly to return to it; PostgreSQL failures never silently switch datasets.

Observation payload text remains immutable alongside JSONB and typed projections. Odds use NUMERIC, date-only evidence uses DATE, and known timezone-bearing timestamps use TIMESTAMPTZ. Unknown times remain null. Provider identities stay separate; similar names do not trigger merges. Different source imports of the same match remain distinct evidence.

AI tools use a separate SELECT-only identity, read-only transactions, validated identifiers, a small SELECT grammar, 1–100 returned rows and a 10-second statement timeout. Functions, compound statements and modification commands are rejected. Raw archival state is not exposed by the query controls. Cloud accounts and billing remain separate from database connectivity.

Use **Create Authorized Backup** for an exported-snapshot pg_dump archive plus a local SQLite control backup. Credentials remain Windows-user/dataset-bound DPAPI files and are excluded. Restore tests target a newly named isolated schema and compare table counts and original payload fingerprints. Archives are private evidence, not public release files. Re-enter credentials when restoring into another Windows account or data directory.

The currently authorized Mission 001 account can create owned schemas but cannot create databases or roles. Its non-superuser account serves runtime, migration and backup purposes with separate protected bindings; a dedicated runtime role remains an administrator prerequisite. The existing read-only account is independent. No privileges are escalated. Separate-database restoration is blocked by CREATEDB permissions; isolated-schema restoration is explicitly labeled.

The existing postgres_engineering MCP server is reused, with its returned connectionId. MCP acceptance compares genuine rows with an independent driver query. pgAdmin is an optional administration client; it is not bundled or required by ordinary application use.

Microsoft SQL Server is no longer an active runtime dependency. Its Windows installation, databases, guard and historical evidence are preserved. Earlier releases are retained for rollback. Do not overwrite an existing running candidate; choose a separate data directory and port.

The packaged Python client needs no developer interpreter. PostgreSQL server and pg_dump/pg_restore/psql utilities must already be installed locally; this installer does not install or reconfigure database services.

Reference protocols: [psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html), [PostgreSQL pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html), [pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html), [Microsoft PostgreSQL MCP](https://github.com/microsoft/postgres-mcp/blob/main/USAGE.md).
