# DRAGONHYDRA 0.2.0-beta.5 · Advanced reference

Available offline. Original evidence remains distinct from predictions and AI interpretation.

## Your first five minutes

Browse saved evidence first. No programming, subscription or new import is needed.

Preferences are stored in this workspace’s SQLite control database. They contain only Beginner Mode and tour completion, not secrets. Help is bundled locally; external documentation links need internet. The previous beta.4 checkpoint contained 5,840 observations: 2,282 COLLECTED, 3,474 IMPORTED and 84 SYNTHETIC. Current counts are queried, not hard-coded.

## Overview

Find out what is stored, where it was read from and whether the application can use it.

PostgreSQL CONNECTED means a read-only transaction succeeded in this application session. NOT_CHECKED means no query has run yet. Last success is a timestamp, not a permanent guarantee. A failed read displays Unavailable, never a misleading zero or an automatic SQLite fallback. PostgreSQL “Query OK” is not a full physical database corruption audit.

## Football research

Search saved match results and inspect safely linked bookmaker prices in plain English.

Search scans at most 10,000 selected observations and returns at most 50 matches per page. Larger datasets require a source filter rather than silent truncation. Links require a match ID within the same source, or a complete exact source/competition/season/teams/date identity. Sources are not merged by similar names. Quotes without enough identity remain available in Sports odds and Historical observations.

## Historical observations

Browse the original saved records and inspect their provenance.

Observations preserve unknown observed_at values. Date-only event fields are not fabricated into midnight timestamps. The table and timeline display one 100-row page; analysis queries the full filtered set up to 10,000 rows. Browser downloads go to your browser’s chosen download folder. CSV formula-like text is escaped for spreadsheet safety.

## Sports odds

Explore retained bookmaker quotations and understand implied probabilities.

Probability is 1/decimal odds, reported as a fraction or percentage. Market probabilities can sum above 100% because of bookmaker margin. A recorded quotation is not necessarily executable, simultaneous with another quote or current. Unknown quote time stays unknown. Numerical summaries of prices are not betting forecasts.

## Numerical intelligence

Summarize compatible numbers with reproducible calculations.

Each calculation requires one source × series × unit × provenance. Zero or multiple compatible scopes are rejected on the server even if a client is bypassed. Maximum 10,000 rows, window 1–1,000. Pearson correlation needs at least three unique pairs at exact known observation times and nonconstant series. Date-only records cannot establish exact-time correlation. The approximate confidence interval assumes independent samples; outlier flags are review candidates. Brier score/log loss require paired probabilities and 0/1 outcomes and do not verify prediction chronology.

## Data sources and CSV imports

Import permitted files without writing JSON for ordinary CSV work.

Upload limit is 20 MiB; CSV/TSV, JSON, JSONL, XLSX, structured XML, supported HTML tables, text PDF and read-only SQLite are supported through their configured readers. PDF text extraction is not OCR. Source ID is a stable internal name; Display name is a friendly label. Configured file/location, field mapping JSON and reader options are advanced controls. HTTP collection requires explicit permission and connected mode. Invalid atomic batches commit no observations. Edit loads existing settings; enable/schedule can start approved background collection; disabling stops future scheduling without deleting historical data.

## Football API Control Center

Configure six independent providers. A configured card is not proof of a connection.

The six identities are APIfootball.com, API-Football/API-Sports, TheSportsDB, Highlightly, football-data.org and OpenLigaDB. They have distinct protocols, budgets and credentials. Anonymous/public-demo providers do not need invented private keys. Local budget counters are not total account usage. HTTP 401/403 may mean invalid credentials or missing feature permission; 429 means stop until retry allowance. Free-plan availability and odds access are provider-controlled. LIVE_PASS means real endpoint acceptance; MOCK_PASS only means isolated protocol regression passed.

## Football Data Comparison

Review agreement, missing information and conflicts without merging original records.

Aliases preserve originals and provide an owner-confirmed comparison mapping. Similar names alone are not identity proof. Providers may share upstream data, so agreement does not establish independent truth. Incomplete identities are explicitly listed instead of force-merged.

## PostgreSQL Control Center

Inspect the real local relational database and its read-only results.

The current installation uses the authorized dragonhydra_intelligence schema within codex_engineering because existing credentials lack CREATEDB/CREATEROLE. AI reads use codex_mcp_ro; runtime/migration/admin currently share an existing non-superuser owner with separate protected credential bindings. Do not change unrelated roles or databases. Supported SQL is simple SELECT columns FROM owned_table LIMIT n, max 100, with functions, joins, writes and compound statements prohibited. Statement timeout 10 seconds, lock timeout 5 seconds. Use preserved SQLite offline explicitly to change datastore; PostgreSQL failure does not silently fall back. Initialize/migrate/activate are advanced operations requiring verified ownership and reconciliation. SQL Server is not an active runtime dependency.

## Recovery Center, backups and restore

Understand task outcomes and preserve recoverable data.

PostgreSQL backups use pg_dump plus a repeatable-read snapshot and a SQLite control-state backup; isolated restore compares table counts and original payload fingerprints. Separate-database restore requires privileges not currently available. Saved API/database secrets are deliberately excluded from public archives and backups. DPAPI credentials are bound to the Windows user and data directory; configure authorized credentials again after moving to another user/path. SQLite backup uses the supported backup API, including committed WAL. SQL Server maintenance evidence remains untouched.

## Cloud AI Control Center

Configure optional AI interpretation without automatically sharing a database.

OpenAI Responses, Claude Messages, xAI, supported Microsoft Foundry/Azure OpenAI/Copilot Studio interfaces, Manus task workflows and compatible local endpoints differ. No purchases or subscriptions are created. Cost may be unknown; local request/output/time limits are not a guaranteed currency cap. Manus tasks may continue remotely until explicitly stopped through supported controls. Cloud interpretations are not database facts. The existing OpenAI live-inference gate was blocked by account credits; mock tests do not establish genuine replies.

## AI Intelligence Cockpit and floating chat

Hold provider-specific conversations while browsing evidence.

Conversations retain company/model/session identity, tool receipts and usage when available. Cloud tools use bounded authenticated application functions, not arbitrary local shell access. Export/copy can include your conversation content; choose recipients carefully. Local inference remains optional. Switching Offline prohibits outbound cloud inference while preserving local research.

## Living Search

Search a local index of permitted supporting sources.

A documentation page supports a capability claim but is not a football observation. URL availability and content fingerprints can change. Models receive only selected bounded knowledge evidence. Registered sources without retrieval are not verified live content.

## AI evidence tools

Run documented bounded queries without requiring a model response.

Read-only templates and identifier allowlists constrain SQL. A tool execution is genuine local computation even when a cloud provider is unconfigured. Returning no rows is distinct from a failed operation.

## Tool registry and MCP extensions

See exactly which capabilities AI agents can request.

Registry argument schemas reject unknown fields. SQL tools use the independent read-only role, max 100 rows and strict statement grammar. External ChatGPT plugins are not automatically compatible with a standalone application. The local MCP interface requires its own scoped authentication. Secrets are not returned to agents.

## Codex engineering

Attach the existing authorized engineering session and inspect its work.

Codex connection needs its existing supported local App Server interface, workspace and thread. Cloud chat does not receive arbitrary shell authority. A missing local worker is a configuration/access limit, not a completed engineering task. Recovery reuses an existing job ID and receipt rather than blindly replaying work.

## Hardware & process monitor

Read real supported computer measurements.

Windows process/service APIs and available NVIDIA-SMI readings are used without installing kernel drivers. Sampling windows affect CPU readings. Per-process network attribution or CPU temperature may not be available. Only task-owned processes are controlled; unrelated services are preserved.

## System diagnostics

Inspect module health and useful error details.

Status receipts distinguish datastore reads from cached historical tests. Error messages exclude credentials. SQL Server, unrelated software and Windows services are not changed to clear tests. Report the failed action, timestamp and receipt path when asking for help.

## Public text & sentiment

Inspect source-backed text and clearly labeled interpretations.

The built-in method is a small English word baseline, not a multilingual trained model. It may abstain on unsupported languages or negation. It does not replace original text or create measured sentiment facts.

## Weather intelligence

Keep actual measurements separate from forecasts.

Observation time, issue time, valid time and retrieval time are different clocks. Unknown values remain missing. A forecast becoming older does not make it an observed measurement.

## Windows launcher and safe shutdown

Open the authenticated application and preserve your workspace.

The launcher verifies service identity and data directory before reuse. Different versions or databases are never silently hijacked. Installed and portable editions use writable user state by default. Uninstall removes owned application files and keeps user databases/credentials. Earlier release folders remain rollback options. Native pointer automation was unresolved in a prior checkpoint; CLI/browser acceptance is recorded separately rather than substituting it for clicks.

## Messages and recovery actions

Read what the application actually knows before retrying.

PASS describes executed acceptance; LIVE_PASS means a genuine external/database result; MOCK_PASS identifies simulated provider protocol tests; NOT_RUN was not executed; PARTIAL has unresolved gates; FAIL has actual failed evidence. PENDING/QUEUED/RUNNING are task progress states; COMPLETE has a committed receipt; INTERRUPTED requires recovery review. Authentication required means reopen through the launcher, never disable security.

## Glossary

**Observation** — One retained measurement or record; not necessarily a unique match.

**Source** — The independently identified origin of a record.

**Series** — One measurement definition, such as total goals or one bookmaker market/outcome.

**Unit** — The measurement scale, such as goals, decimal odds or degrees Celsius. Unknown is an explicit missing unit, not an invented one.

**Provenance** — How a record originated and which source/evidence supports it.

**IMPORTED** — Brought into the application from a file or historical dataset.

**COLLECTED** — Acquired through a collection process; not automatically live or current.

**SYNTHETIC** — Fictional demonstration or test data. Never treat it as measured football evidence.

**INFERRED** — Derived or predicted information, not a directly observed fact.

**VERIFIED** — Passed the specifically documented check; it does not prove every source claim true.

**UNCERTAIN** — Evidence or interpretation has unresolved limitations.

**INVALID** — Failed a stated validation rule.

**SPORTS_RESULT** — A saved sports result or result-related measurement; inspect the original score and status.

**SPORTS_ODDS** — A retained bookmaker quotation.

**FOOTBALL_RECORD** — A structured football entity such as a competition, team, fixture or standing; not necessarily numerical.

**NUMBER** — A numerical measurement whose meaning is defined by its series and unit.

**PRICE** — A price measurement in its stated unit.

**SHORT_TEXT** — Source-backed text.

**WEATHER_OBSERVATION** — An actual weather measurement.

**WEATHER_FORECAST** — A prediction with separate issue and validity times.

**Mean** — Arithmetic average: sum divided by count.

**Median** — Middle value after sorting.

**Standard deviation** — A measure of how spread out numerical values are.

**Outlier** — A value flagged for review; not automatically an error.

**Correlation** — A mathematical association, not proof that one variable caused another.

**Confidence interval** — A method-dependent uncertainty range whose assumptions must hold.

**Decimal odds** — Bookmaker price including stake in the gross return; historical prices are not current offers.

**Implied probability** — 100 divided by decimal odds, as a percent; bookmaker margin remains.

**Observed time** — When the source says a measurement was observed.

**Collection time** — When DRAGONHYDRA retrieved or imported it.

**Date only** — Calendar date without reliable time-of-day or timezone. No midnight is invented.

**Fingerprint / SHA-256** — A content identifier used to detect changes; not proof that source content is true.

**Duplicate** — A record identity already retained; its original evidence stays unchanged.

**Receipt** — The recorded outcome of an import, query, calculation or tool action.

**PostgreSQL** — The selected relational database platform; requires an authorized local connection.

**SQLite offline** — An explicitly selected local datastore and the application control-state store.

**Schema** — A named collection of database tables with defined ownership.

**Read-only** — Queries may read authorized data but cannot change it.

**MCP** — A protocol for invoking defined tools; registration alone is not connection acceptance.

**DPAPI** — Windows user-scoped protection for saved credentials. Moving encrypted files to another user/path may require re-entry.

**CSRF** — Session protection against unrelated sites triggering changes through your browser.
