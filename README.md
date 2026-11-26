# DRAGONHYDRA Next Generation

Install the [Android edition](docs/distribution/ANDROID.md) or the [Python wheel and programming API](docs/distribution/PYTHON.md). The [distribution guide](docs/distribution/BUILD.md) connects each package to its build and acceptance procedure.

A local-first sports intelligence application for inspecting source records, comparing historical bookmaker prices and evaluating probability models. Version **0.3.0-beta.1** continues DRAGONHYDRA SCRAPP INTELLIGENCE.

[Download the Windows prerelease](https://github.com/chatgptopenaiagi/DRAGONHYDRA-SCRAPP-INTELLIGENCE/releases/tag/v0.3.0-beta.1) · [User guide, architecture and formulas](docs/next-generation/PLATFORM.md) · [Validation report](docs/RELEASE-0.3.0-beta.1.md) · [Roadmap](docs/next-generation/ROADMAP.md)

## Start on Windows

Extract the portable ZIP, then open DragonhydraIntelligence.exe. The installer also installs the same application for the current Windows user. Choose a data directory and a free port in the native launcher, then select **Start / open dashboard**. The first run opens an empty offline workspace. An existing SQLite workspace gets a verified backup before the history index is installed.

- **Sports desk** shows collected ESPN events for the Premier League, NBA, NHL, MLB and NFL. Choose a date and league. Switch to configured connections to collect a scoreboard. Saved events, revisions and model evaluation remain available offline.
- **Football research** shows source-scoped matches and quotes. Inspect a bookmaker snapshot, compare timestamped price movements, or export the source IDs behind a calculation.
- **Sports odds** converts decimal, American and fractional prices. Calculate proportional fair odds, overround and an expected value under an explicitly named probability assumption.
- **Historical model evaluation** compares frozen league outcome frequencies with a uniform model on independent seasons in England and Germany. The dashboard includes sample sizes, calibration and pinned source documents.
- **Data sources and recovery** retain CSV import, six football adapters, original observations, task receipts, SQLite backup/restore and optional PostgreSQL. Model assistance uses explicit configuration. Core calculations run locally.

## Develop and verify

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-build.txt
.\.venv\Scripts\python -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python application/living_launch.py
```

The historical SQL Server adapter remains available for legacy unit verification. The current analytical stores are SQLite and optional PostgreSQL. The distribution supplement adds an offline Android application and an installable Python wheel to the original Windows x64 and source release. No live bookmaker feed is bundled. Stored odds, calculated market weights and model estimates have distinct provenance.

Older guides remain available for [football provider configuration](docs/mission-005/FOOTBALL-API-COST-COMPARISON.md), [the conversation cockpit](docs/mission-006/AI-COCKPIT.md) and [PostgreSQL](docs/mission-006/POSTGRESQL.md). See [AGENTS.md](AGENTS.md) for development and release procedures.
