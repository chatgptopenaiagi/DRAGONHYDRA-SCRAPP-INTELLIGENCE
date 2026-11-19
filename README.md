# DRAGONHYDRA SCRAPP INTELLIGENCE

Windows corrective beta **0.2.0-beta.2**: preview, map and atomically import CSV files; configure six independent football data providers; compare retained source evidence through an authenticated local dashboard.

Download the portable ZIP or per-user Windows installer from the [beta release](https://github.com/chatgptopenaiagi/DRAGONHYDRA-SCRAPP-INTELLIGENCE/releases/tag/v0.2.0-beta.2). Extract the ZIP and open **DragonhydraIntelligence.exe**, then **Start / open dashboard**. No development Python or Conda installation is needed. New installations start empty; private datasets and API keys are never bundled. State is stored in the current user's local application data directory, separately from program files. Port 18977 is the default; **Find free port** safely selects another port.

## Import and connect

**Data sources → Import Data** previews CSV/TSV encoding, headers and rows. Create a source in the wizard, inspect column dropdowns, validate, confirm and open the actual imported records. Numerical and football profiles preserve original cells, dates, unknown timestamps and historical odds provenance. Other readers support JSON, JSONL, XLSX, structured XML, a single HTML table, text PDF and read-only SQLite.

**Football API Control Center** contains APIfootball.com, API-Football (API-Sports), TheSportsDB, Highlightly, football-data.org and OpenLigaDB. Provider identities, parsers, credentials, request budgets and receipts are separate. TheSportsDB's public demonstration endpoint and OpenLigaDB passed real online acquisition. All six passed controlled mock scenarios. The four private-key providers require the owner's permitted credentials and have **not** passed live authenticated acceptance. Mock success is not live success.

Mandatory subscription cost is **€0**. Online operations require Configured connections, explicit enablement and permission. Schedules are off by default. No paid plan is purchased or activated. Odds availability depends on documented provider entitlement and has not been established by a live odds response. Football-Data.co.uk is supported as historical CSV, not a live API. Football Charts is researched as an optional seventh provider and is not implemented.

Keys are entered in the authenticated dashboard and protected using Windows user-scoped DPAPI. They are excluded from normal database backups, exports, logs and packages. Re-enter credentials when moving to another Windows account or dataset directory. Offline mode blocks outbound collection. Match comparisons preserve originals and flag uncertain identity or conflicts; agreement does not establish truth or independent upstream lineage.

Read the [user guide](docs/mission-005/USER-GUIDE.md), [security and contracts](docs/mission-005/SECURITY-AND-CONTRACTS.md), [provider cost comparison](docs/mission-005/FOOTBALL-API-COST-COMPARISON.md) and [endpoint inventory](docs/mission-005/FOOTBALL-API-ENDPOINT-INVENTORY.json).

## Beta boundaries and rollback

Preserved beta.1 remains available under its original tag. Schema-3 migration keeps a pre-migration database copy; beta.1 rollback requires that copy in a separate dataset directory. SQL integration remains BLOCKED pending the existing maintenance authority. Live Joomla communication, optional AI endpoints, private-key provider access and live bookmaker feeds are not certified. Event/player-statistic contracts are extension points, not enabled data categories. Unsigned Windows binaries may prompt a Windows trust warning. An interrupted installer can retain unused staging files for inspection; user data is preserved. This release is not production certification.

## Source development and tests

Use Python 3.12 or newer and requirements.txt in an isolated environment. Run `python application/living_launch.py` and `python -m unittest discover -s tests -p "test_mission*.py" -v`. DPAPI tests require Windows. The private owner CSV is intentionally absent; set `DH_ACCEPTANCE_CSV` to an authorized copy to run its specific 217-row acceptance. Public tests otherwise report that case skipped.

Edge workflow tests use the installed Microsoft Edge and requirements-test.txt. `python tests/mission005_csv_browser.py --exe PATH_TO_EXE --csv PATH_TO_CHAMPS_CSV` exercises the owner-file workflow; `python tests/mission005_provider_browser.py --exe PATH_TO_EXE` uses six isolated mocks. Add `--live` only for bounded requests to the documented public providers. Never insert private keys into tests.

Windows packaging reuses PyInstaller via requirements-build.txt and `python tools/build_windows.py --mission 005 --version 0.2.0-beta.2`. The distributed application does not depend on these developer tools. Third-party runtime notices accompany binaries. This repository does not grant a license to any third-party dataset.
