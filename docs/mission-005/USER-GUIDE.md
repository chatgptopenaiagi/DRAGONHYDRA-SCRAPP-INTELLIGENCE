# DRAGONHYDRA SCRAPP INTELLIGENCE 0.2.0-beta.2

Open **DragonhydraIntelligence.exe**. Select a data directory and Offline or Configured connections, then Start / open dashboard. The default local port is 18977. If another service occupies it, select **Find free port**. The launcher verifies the running service's dataset identity before sending its credential. Closing the launcher leaves the service running; **Stop gracefully** closes it safely.

Application data is stored under `%LOCALAPPDATA%\DRAGONHYDRA\LivingIntelligence` unless you select another location. Installation files and portable files contain no private datasets or API keys. A portable program can therefore run from a read-only folder while retaining state in the user's writable data directory. Keep separate data directories when comparing beta versions.

## Import a CSV

1. Open **Data sources → My local datasets · Import Data**.
2. Choose CSV / TSV file and Preview file. Review filename, size, encoding, delimiter and original rows. If Windows encoding detection is uncertain, select the known encoding and preview again.
3. Select an existing upload source, or enter a source ID/name and click **Create source for this file**. Use Imported for genuine external records; Synthetic is only for fixtures and demonstrations.
4. Inspect the profile, column dropdowns, date convention and decimal convention. Supply a competition and season only when you know them. Blank clocks stay unknown.
5. Validate records. Review physical row numbers and reasons. Invalid batches commit no observations. Correct the file or mapping and validate again.
6. Confirm atomic import. Progress leads to an inserted/duplicate receipt. Open imported observations or Analyze imported values.

CSV limits: 20 MiB, 100,000 rows and 100,000 expanded observations, at most 500 unique headers. CSV/TSV supports quoted delimiters, multiline fields, UTF-8/BOM and explicitly selected Windows encodings. A rejected batch is never silently truncated. Football-Data.co.uk columns Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR and B365H/D/A have suggestions. Other bookmaker columns can be mapped explicitly. Closing and pre-closing prices should use separate sources/profiles. `champs.csv` supports decorated English dates, Team 1/2, FT and its `(*)` extra-time marker; original ET, penalty and aggregate cells remain inspectable.

Use the other local readers for JSON, JSONL, XLSX, XML, one HTML table, text PDF and read-only SQLite. Advanced source mappings remain available there. Unsupported OCR is not advertised as extraction.

## Connect football sources without a mandatory subscription

Open **Football API Control Center**. Six cards identify the actual providers. Each card starts unconfigured; collection is never scheduled automatically. Select Configured connections and Apply mode. Enable only the provider you intend to use and confirm permitted free access. Save configuration, then save its key where required. Keys are entered here, never in a terminal.

APIfootball.com, API-Football/API-Sports, Highlightly and football-data.org require independently issued credentials. TheSportsDB uses its documented public v1 demonstration key. OpenLigaDB needs no key. Direct provider accounts are supported; RapidAPI-issued credentials are not interchangeable with direct credentials.

**Test connection / discover competitions** makes bounded real requests and validates the response. Select a returned competition, data category and season; save configuration; then **Collect now**. APIfootball.com needs a bounded from/through date range for matches or odds. OpenLigaDB can restrict match collection to one matchday. TheSportsDB team search accepts a team name such as Arsenal.

Status means what happened: CONFIGURED has no successful connection proof; CONNECTED means the most recent operation succeeded; OFFLINE blocks online operations; AUTHENTICATION_FAILED, RATE_LIMITED and UNAVAILABLE explain failures. A zero-row success does not prove data coverage. Test receipts do not pretend to have imported records. Read collection receipts for actual inserted and duplicate counts.

Polling is opt-in and budgeted. Local counters are estimates of this application's usage, not your provider account's complete usage. HTTP 429 pauses subsequent requests until the retry time. Limits and a conservative rolling-day cap prevent uncontrolled polling. No paid plan is activated, no purchase is made, and premium-only Highlightly odds and TheSportsDB v2 endpoints are disabled.

## Compare and preserve evidence

Football Data Comparison filters retained records by source, category, competition, season, team and dates. Exact identities and explicit owner-confirmed aliases generate comparison candidates. Original provider IDs and payloads remain separate. Agreement does not establish truth or independent upstream lineage; uncertain matches are never merged. Score periods must agree before comparing goals.

Recovery Center retains queued, interrupted, cancelled, blocked and failed tasks. Resume validates the staged original and committed receipt again. Create verified backup preserves the SQLite database. Restore through the native launcher closes the selected candidate and backs up its current database before replacement. Previous schema migrations also preserve a pre-migration copy.

## Credentials and rollback

Private keys use Windows user-scoped DPAPI, bound to this data directory and provider slot. Saved keys are never returned to the browser. Show/hide affects only a newly entered key. Remove key deletes the local credential; revoke it at the provider if necessary. SQLite backups and exports exclude credentials. Restoring a backup to the same dataset retains the separate current credential files. Moving to another Windows account or data directory requires re-entering keys. Never distribute the private directory with a portable package.

The beta.1 portable archive, installer and Git tag remain the rollback baseline. Do not open a schema-3 database with beta.1. Restore its preserved pre-schema-3 backup into a separate data directory using the original launcher. Original 0.1 data and its port 18975 remain independent.

An interrupted installer can leave an unused `.stage-...` directory next to the selected installation folder. A subsequent installation uses a fresh staging directory; the installed program and data remain intact. These interruption remnants are retained for inspection rather than automatically deleted. Normal uninstall removes registered application files and owned rollback programs while retaining user data and unrelated files.

SQL integration remains blocked by the existing maintenance authority. Joomla communication for this beta, optional AI engines and live authenticated access to the four keyed providers are not certified by offline or mock tests. This is a beta, not a production certification or a live betting service.
