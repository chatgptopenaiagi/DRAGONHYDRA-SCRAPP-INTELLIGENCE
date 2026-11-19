# DRAGONHYDRA 0.2.0-beta.5 · Beginner guide

Available offline. Original evidence remains distinct from predictions and AI interpretation.

## Your first five minutes

Browse saved evidence first. No programming, subscription or new import is needed.

1. Open the verified DRAGONHYDRA shortcut. A one-use login exchange opens your local dashboard. If a session expires, reopen it from the launcher.
2. Read Overview: check the count, the datastore that supplied it and the time of that read. Counts are observations, not unique football matches.
3. Open Football research. Search a team such as Arsenal, then open a result. Read the source, provenance, date and any recorded bookmaker prices.
4. To calculate statistics, choose a compatible series in the guided selection box. Use full series sets its source, series, provenance and unit for you.
5. Use Help or F1 anywhere. Beginner Mode adds guidance; switching it off does not remove records or disable features.

Example: Try Football research → Arsenal → Search matches → Inspect result. A missing odds panel means no safely linked quotations were found, not zero probability.

## Overview

Find out what is stored, where it was read from and whether the application can use it.

1. Retained observations counts records in the selected datastore. One match can have a result and several odds quotations; separately attributed imports remain separate evidence.
2. Read the data-source banner. PostgreSQL and SQLite offline are different datastores. Offline connection mode only disables external APIs; it does not prevent local PostgreSQL queries.
3. Use Test PostgreSQL connection for a genuine read-only version and identity query. Refresh re-reads data; it does not collect from football APIs.
4. Use the provenance cards to distinguish imported, collected and synthetic evidence. Recent activity describes actual local operations.

Example: 5,840 observations plus PostgreSQL CONNECTED means that count was returned by a real PostgreSQL query at the displayed read time.

## Football research

Search saved match results and inspect safely linked bookmaker prices in plain English.

1. Enter a team, competition or season, or leave search blank. Select a source and provenance if you want to narrow the results.
2. Dates restrict the match calendar date, where supplied. Unknown dates are kept unknown. Search matches applies your selection; Previous and Next move through pages.
3. Open a result to see the original source fields, collection time and evidence hash. A missing score is shown as Not supplied, never guessed.
4. Open Recorded odds to view bookmaker, market, outcome, decimal price and known quote time. Inspect quote shows the underlying observation.
5. Read the probability explanation: decimal odds 2.50 imply 100 ÷ 2.50 = 40%. This includes bookmaker margin and is not a calibrated prediction or a promise of profit.

Example: Search Arsenal in the historical football source. A 1–0 result and a saved 1X2 quotation describe different records with different provenance clocks.

## Historical observations

Browse the original saved records and inspect their provenance.

1. Choose Source (where data came from), Kind (what type it is), Provenance (how it was acquired), Series (one measurement) and Unit (how it is measured). All means no restriction.
2. Search evidence looks through stored record content, including team names and metadata. Apply updates the table. Clear filters removes restrictions.
3. Collection time range uses UTC retrieval time, not the date a match was played. Use Football research for match-date searches.
4. Inspect opens the exact evidence, original fields, hash and validation warnings. Close or Escape returns to the table.
5. Export CSV and Export JSON download the current filter selection. Check the documented 10,000-record export limit; export narrower ranges for larger selections.

Example: Filter IMPORTED + SPORTS_RESULT, search Chelsea and click Apply. Clear filters if “No records match” appears unexpectedly.

## Sports odds

Explore retained bookmaker quotations and understand implied probabilities.

1. Select an odds source and IMPORTED or COLLECTED provenance. SYNTHETIC contains fictional demonstration prices.
2. Choose one odds series and its decimal unit before analyzing prices. A home-win price and a draw price are different series.
3. Enter decimal odds greater than 1 and press Calculate implied probability. The calculation uses your entered price; it does not fetch a current bookmaker offer.
4. View historical results changes the table’s record category. Clear filters if a previously selected odds series hides match results.

Example: Decimal odds 2.00 imply 50%; 4.00 imply 25%. These arithmetic conversions do not establish the real chance of a result.

## Numerical intelligence

Summarize compatible numbers with reproducible calculations.

1. Pick a ready-to-analyze series from the guided list and press Use full series, or select source, series, provenance and unit manually.
2. Apply loads the matching records. Analyze selected series calculates statistics only after the selection is compatible. An incomplete selection opens helpful guidance without a red error.
3. Count is how many numerical records were used. Mean is the average. Median is the middle value. Minimum and maximum show the range; sample spread describes variation.
4. Moving average window is a number of records, not days. Inputs, method and uncertainty shows IDs, exact values, algorithm version, fingerprint and limitations.
5. Advanced users can compare two exact-time series or evaluate previously recorded binary predictions. Read the matching requirements before interpreting these results.

Example: Choose football.total_goals with the goals unit and IMPORTED provenance. Do not combine total goals with decimal odds or synthetic prices.

## Data sources and CSV imports

Import permitted files without writing JSON for ordinary CSV work.

1. Use Import Data, choose CSV, then Preview. Confirm the filename, detected encoding, delimiter and visible rows.
2. Select an existing source or Create source for this file. A source is the name under which the imported evidence will remain traceable.
3. Choose the schema profile and map columns with dropdowns. Confirm date format, decimal convention and units. Unknown times must remain unknown.
4. Validate, review rejected rows and warnings, then Confirm import. Follow progress and inspect the receipt’s inserted, duplicate and rejected counts.
5. Open imported observations or Analyze imported values. Re-importing the same records should report duplicates, not create extra observations.

Example: For a football CSV map Date, Home team, Away team, Home goals and Away goals. “0 inserted, 3040 duplicates” means those records were already retained.

## Football API Control Center

Configure six independent providers. A configured card is not proof of a connection.

1. Choose Offline for local research or Configured connections for explicitly enabled providers. No subscription is activated automatically.
2. Save the provider configuration, enter its own API key when required and Save / replace API key. Saved keys are masked and never sent back to the browser.
3. Test authentication or Test connection / discover competitions. Read the actual result and quota. Choose a supported competition, season and data category.
4. Collect now performs one approved acquisition. View import results shows the real receipt. Enable scheduled collection only if you want recurring requests.
5. Remove configuration disables that provider without deleting historical observations. Remove saved API key removes the local secret; revoke it at the provider if needed.

Example: Start with the provider already configured by the owner. Test first, choose a supported historical season, collect once, then inspect the receipt.

## Football Data Comparison

Review agreement, missing information and conflicts without merging original records.

1. Filter by source, competition, season, team, dates and category; press Compare retained sources.
2. Open each source record to compare identities, dates, score period and values. SINGLE_SOURCE is not corroboration.
3. AGREEMENT_CANDIDATE means matching candidate records agree. CONFLICT_REQUIRES_REVIEW means their recorded values differ.
4. Only use Explicit identity aliases when you have independently confirmed that two names refer to the same entity.

Example: Compare two providers’ Arsenal fixtures on the same date, competition and season, then inspect their source IDs before accepting agreement.

## PostgreSQL Control Center

Inspect the real local relational database and its read-only results.

1. Test Connection executes a real version and identity query. Discover PostgreSQL only discovers local service/client details; it does not by itself prove a login.
2. Refresh Databases lists accessible catalog entries. Select Database changes configuration only when safe; credentials are bound to the selected endpoint and database.
3. View Schemas and Inspect Tables discover real objects. Describe Columns explains types. Browse Sports Records and Run Read-only Query return bounded rows.
4. View Import Receipts shows retained import evidence. Check MCP compares a real MCP SELECT with an independent driver query.
5. Create Authorized Backup makes a verified archive. Test Restore in Isolation creates a separate owned schema; it never overwrites the original research schema.

Example: SELECT id,kind,origin FROM observations LIMIT 10 returns ten saved identities. “NOT_CHECKED” asks for a test; “AUTHENTICATION_FAILED” asks you to check the saved authorized login.

## Recovery Center, backups and restore

Understand task outcomes and preserve recoverable data.

1. Queued tasks are waiting; Running tasks show real progress. Open Receipt / details to inspect results.
2. Failed, Blocked, Interrupted or Cancelled tasks keep their evidence. Correct the reason before Resume; cancellation does not undo already committed records.
3. Create verified backup uses the selected datastore. For PostgreSQL, inspect and test restore in PostgreSQL Control Center. For SQLite, restore through the native launcher.
4. Keep old releases and verified backups. Do not restore over original research merely to test a backup.
5. Revoke browser sessions signs browsers out. Reopen through the launcher to authenticate again.

Example: A cancelled upload can be retried after inspecting its task. A completed duplicate-only import is successful preservation, not data loss.

## Cloud AI Control Center

Configure optional AI interpretation without automatically sharing a database.

1. Choose a supported developer provider and model/deployment. A consumer chat subscription is not necessarily API access.
2. Save a protected credential, enable the configuration and test connection. Quota or missing credits can block inference even if authentication works.
3. Choose specific records, load them, then Preview selected data. Review exactly what will leave the computer.
4. Approve and Send only the intended request. Inspect its returned text, usage and receipt. Stop or inspect a remote task when that provider supports it.

Example: Select five football records and ask “Summarize only these results and cite source IDs.” Inspect the preview before allowing a cloud request.

## AI Intelligence Cockpit and floating chat

Hold provider-specific conversations while browsing evidence.

1. Configure a provider and Open chat. Select an available model, write a message and Send. The response must come from that configured provider.
2. New conversation creates separate history; Search history finds earlier sessions. Changing provider does not transfer a previous conversation’s sharing approval.
3. Move or resize the floating window, Dock right, Expand, Minimize or Restore. These only change layout.
4. Inspect cited tools and source records. Stop response stops local waiting/cancels where supported; Retry repeats the failed operation deliberately.
5. For a roundtable, explicitly select each provider and approve separate requests. Unconfigured companies do not receive messages or produce fake replies.

Example: Ask a connected provider to query a bounded set of stored football results. Inspect the tool receipt instead of trusting an unsupported database count.

## Living Search

Search a local index of permitted supporting sources.

1. Enter search text and search indexed titles, tags and retrieved content. This is not unrestricted web crawling.
2. Inspect a source’s title, URL, discovery/refresh date and evidence fingerprint.
3. Create or edit an approved source with a useful title and tags. Enable retrieval only for that permitted URL.
4. Refresh on demand, or deliberately enable scheduled refresh. Offline mode still allows searching previously stored knowledge.

Example: Search “PostgreSQL backup” to find indexed documentation and inspect when it was last retrieved.

## AI evidence tools

Run documented bounded queries without requiring a model response.

1. Choose a documented tool, source and row limit. Fill only its supported arguments.
2. Run selected read-only tool and inspect the returned rows, source IDs and execution receipt.
3. Use schema descriptions to understand fields before requesting data.

Example: Choose football results and a limit of 10, then inspect the ten returned source records.

## Tool registry and MCP extensions

See exactly which capabilities AI agents can request.

1. Select a tool to read its description, permissions and argument fields. Enable or disable only the tools you intend to offer.
2. Run a bounded read and inspect the receipt. Data-changing requests stage an explicit application action rather than granting a model a shell.
3. For MCP, configure a separate local credential and inspect actual connection status. A registered connector is not proof that a query succeeded.

Example: Use get_postgresql_status or run_bounded_postgresql_select and inspect the execution result before discussing it with a model.

## Codex engineering

Attach the existing authorized engineering session and inspect its work.

1. Connect to the existing local Codex thread for this project. The application does not start a competing worker.
2. Submit a bounded diagnostic only within the owner’s authorized project. Read its job status and saved result receipt.
3. Inspect the current checkpoint, modified files, processes and test evidence where available. Reconnect after interruption.

Example: Request “Read the latest acceptance report and summarize the failed checks; do not change code.”

## Hardware & process monitor

Read real supported computer measurements.

1. Refresh to sample CPU, memory, disk and monitored process data.
2. Read the timestamp and units. Percentages, bytes and temperature are different measurements.
3. UNAVAILABLE means no reliable sensor or permission exists; it does not mean zero load or zero temperature.

Example: Compare application RAM usage across refreshes, rather than interpreting one idle CPU sample as a performance benchmark.

## System diagnostics

Inspect module health and useful error details.

1. Read each module’s state and dependencies. READY means that component initialized, not that every external provider is live-connected.
2. Open Full status and integration limits for sanitized technical details.
3. Optional local interpretation needs an explicitly configured loopback endpoint and model. Save configuration, then Explain current filtered evidence if intended.

Example: If the observation count is Unavailable, test the selected PostgreSQL connection before changing any source settings.

## Public text & sentiment

Inspect source-backed text and clearly labeled interpretations.

1. Choose retained text records and inspect their source before interpretation.
2. Interpret retained text runs the built-in method and shows the result for each observation.
3. Read method limitations rather than treating a label as an observed fact.

Example: Inspect a textual observation, then compare the method explanation with the actual words.

## Weather intelligence

Keep actual measurements separate from forecasts.

1. Measurements selects weather observations. Forecasts selects predictions.
2. Inspect geography, unit, observation time, forecast issue time and valid time.
3. Use one compatible series for a chart or analysis; never mix cities, units or measurement and forecast classes without an explicit method.

Example: A forecast issued Monday for Wednesday is not a Wednesday weather observation.

## Windows launcher and safe shutdown

Open the authenticated application and preserve your workspace.

1. Start / open dashboard starts or reuses the service for the selected data directory, then opens a one-use authenticated browser session.
2. Choose Offline or Configured connections. Find free port sets port 0; the launcher chooses a free port without stopping another application.
3. System health, Data sources, Active tasks and Diagnostics open those dashboard pages. Selected database displays the actual selected datastore.
4. Create verified backup uses the active datastore. Restore opens the supported isolated PostgreSQL workflow or a confirmed SQLite restore with a pre-restore backup.
5. Stop gracefully ends this workspace’s worker. Closing the launcher alone leaves the service running. Revoke browser sessions logs browsers out.

Example: If a port is occupied, choose Find free port. Never stop an unrelated service to claim the port.

## Messages and recovery actions

Read what the application actually knows before retrying.

1. No data found: clear filters or choose a source with observations. Empty is not a database failure.
2. Choose one compatible series: use the guided source/series/unit/provenance selection, then analyze again.
3. NOT_CHECKED: no query has run this session. CONNECTED: a real query succeeded at the shown time. FAILED or AUTHENTICATION_FAILED: inspect the reason and test again after correcting it.
4. OFFLINE: external requests are disabled; saved records and local database functions still work. CONFIGURED: settings exist, but connection success is not established.
5. RATE_LIMITED: wait until the provider’s retry time. BLOCKED: the required permission, configuration or access is missing. UNAVAILABLE: a measurement or service could not be obtained.
6. 0 inserted with duplicates: matching observations were already retained. Invalid atomic batch: no partial observation set was committed.

Example: If authentication works but an AI reply reports insufficient quota, usable account credits may be missing. Repeated retries do not fix billing access.

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
