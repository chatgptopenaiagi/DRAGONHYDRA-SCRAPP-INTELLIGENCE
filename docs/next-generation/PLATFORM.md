# Sports intelligence and odds analysis

## Using the Windows release

Extract the entire portable ZIP and open `DragonhydraIntelligence.exe`, or run the per-user installer. Choose a data directory and a free port in the launcher. **Start / open dashboard** opens an authenticated loopback session. A fresh directory starts empty in Offline mode. Data files and settings live outside the installation. Use the Recovery center for backups, task receipts and graceful shutdown.

Open **Sports desk**, choose a league and date, and select **View saved events**. In configured connected mode, **Collect from ESPN** queues a request for that scoreboard date. The dashboard remembers your date and league in the current browser origin. Saved events require no internet connection. An empty day can have a successful collection receipt. An absent event remains in history. A collection date, the scheduled start of a match and the time a price was quoted are separate clocks. The original capture is available through the observation ledger and the source content hash in the receipt. League dates follow the provider's schedule.

In **Football research**, filter by source, team or season. Expand an event's recorded odds to inspect its price, origin and original observation. **Historical market movement** plots only timestamped observations for that event, separated by outcome, market terms and bookmaker. Select a market to inspect its table or download the movement ledger. Synthetic examples stay labeled. Actual archive records with unknown quote times can still be inspected.

In **Sports odds**, choose an exhaustive market, choose a number format and enter its prices. The optional expected-value input requires an outcome, a probability in [0,1], and a written basis. Download the calculation to reproduce it. **Explain with local AI** uses the existing explicitly configured loopback endpoint in Diagnostics. Its input comes from the deterministic calculator. Answers have an AI interpretation label and an input fingerprint. Disabled or unavailable inference leaves the calculation available.

Expand **Historical model evaluation** in the Sports desk. Choose a competition to compare frozen preseason estimates with the uniform baseline. Export includes data URLs, byte hashes, frequencies and observed calibration gaps. These results describe historical samples. Neither model accounts for individual teams, injuries, lineups or current form.

## Architecture and storage

The Windows launcher opens the local Python HTTP server and holds a dataset-scoped credential. The browser exchanges a short-lived ticket for a session. Writes require same-origin session/CSRF validation or local launcher authentication. Static assets are bundled. The native launcher, receipts, existing CSV workflow, six football adapters, optional PostgreSQL, existing research views and offline manual descend from SCRAPP INTELLIGENCE beta.5.

| Layer | Main files | Responsibility |
|---|---|---|
| Interface | `application/living/web/{app,beginner,markets}.js`, `index.html` | Dashboard, authenticated requests, local preferences, keyboard-accessible forms, market chart and table |
| HTTP and lifecycle | `server.py`, `launcher.py`, `core.py` under `application/living` | Session, explicit datastore, source configuration, durable worker, recovery |
| Sources | `acquisition.py`, `scoreboards.py`, `football_providers/`, `provider_manager.py` | Bounded response, validated provider contract, immutable original, import receipt |
| Store | `normalization.py`, `storage.py`, `datastore.py`, `postgres_store.py`, `postgres_schema.py` | Normalize clocks and provenance, deduplicate original observations, persist transactional receipts |
| Analysis | `football_research.py`, `market_history.py`, `market_analysis.py`, `analytics.py`, `application/dragonhydra/market_signals.py` | Conservative matching, source-linked movement, Decimal calculations, descriptive statistics |
| Evaluation | `tools/backtest_seasons.py`, bundled `web/backtest.json` | Reproducible chronological test partitions and offline aggregate report |
| Assistance | `connectors.py`, `conversations.py`, `tool_registry.py` | Optional explanations and existing bounded evidence tools |

SQLite schema 3 is the default. `observations` has immutable payloads keyed by content-derived ID, source, series, kind, unit and origin. Update/delete triggers protect originals. `receipts` records a whole import and its counts. Other tables store sources, queued tasks, diagnostics, aliases, saved analyses and component state. The new expression index matches the existing display order across observation time, supplied date and collection time. Existing databases receive a verified SQLite backup before index creation. Table and payload formats are compatible with beta.5. No server migration is required. PostgreSQL remains an optional explicitly selected loopback backend with a SQLite control plane. See [the PostgreSQL module guide](../mission-006/POSTGRESQL.md).

The original Odds Mirror demonstrated exact-set normalization, immutable snapshots, conservative identity matching and withholding calculations on incomplete markets. This release reuses the DRAGONHYDRA core conversion engine already in the application and applies those principles to the active SCRAPP datastore. It does not depend on the mirror's third-party research collection.

## Provider and export contracts

| Interface | Input | Output |
|---|---|---|
| `POST /api/scoreboard/collect` | `league` in nba, nhl, mlb, nfl, eng.1 and ISO `day` | Task ID for a single ESPN scoreboard, fixed HTTPS host and sport path. Connected mode only |
| `GET /api/scoreboard/events` | Same league and day | `dh.scoreboard/1`, archived events, origin, retrieval time, source URL, immutable IDs and latest receipt membership |
| `GET /api/football/research` | Source, origin, search, date bounds, page and offset | Source records, scoped quotes, data-quality counters and per-market history |
| `POST /api/market/calculation` | `market`, `format`, named `prices`, optional `assumption` | `dh.market/1`, exact scenario inputs, stringified decimal outputs and assumptions |
| `GET /backtest.json` | None | Bundled aggregate data and pinned input manifest, `dh.preseason-evaluation/1` |
| `GET /api/export.json` and `/api/export.csv` | Ledger filters, limit and offset | Observations, source IDs, timestamps and hashes. JSON includes nested evidence. CSV is a flat projection |

For example, submit `{"market":"1X2","format":"fractional","prices":{"home":"3/2","draw":"2/1","away":"9/5"},"assumption":{"outcome":"home","probability":"0.4","basis":"User scenario"}}`. Calculation JSON, event JSON and movement JSON retain original identities or exact input strings. Inputs from a file can never authenticate their own provenance.

The six named football adapters have distinct request/parse contracts, quota settings, last-success state and receipts. They include TheSportsDB, OpenLigaDB, API-FOOTBALL (API-Sports), APIFootball.com, Highlightly and football-data.org. A working public schedule or result request does not establish live bookmaker coverage. Each ESPN collection is event-only. No documented quote timestamp is inferred from an ESPN event. Values of `null` mean unknown. The raw source record is retained for statistical and provider review. ESPN's public scoreboard interface is an external dependency with no availability guarantee.

The source classifications are provider-reported, imported historical, synthetic, inferred or unknown. A hash verifies bytes or replay identity. Independent agreement on the underlying event requires separate evidence. Calculator output is tagged mathematical calculation, historical model evaluation is tagged statistical estimate, and optional language-model output is tagged AI interpretation.

## Mathematics and time

For decimal price d > 1, raw implied probability is 1/d. A fraction a/b maps to 1+a/b for positive integers a and b. American A ≥ 100 maps to 1+A/100 and A ≤ −100 to 1+100/|A|. Nonfinite numbers, invalid denominators, incomplete sets and ambiguous odds formats are rejected. Calculations use 34 significant decimal digits for the scenario engine.

For mutually exclusive, exhaustive outcomes, Q = Σ1/dᵢ, overround = Q−1, theoretical bookmaker margin = 1−1/Q, proportional normalized weight wᵢ = (1/dᵢ)/Q, and proportional fair decimal = 1/wᵢ. Margin is a theoretical balanced-book quantity. These transformations produce market weights. Expected net return per unit under a supplied probability p is p·d−1. No modeling of pushes, fees, market execution or fills is included.

Movement uses the earliest and latest **recorded** timestamped points. A reported opening or closing requires an explicit phase label. The change in implied probability is 1/d_last−1/d_first. Volatility is the population standard deviation of adjacent valid log price ratios ln(d₂/d₁), with at least two ratios. It is observation-based and unannualized. Suspended observations and contradictory same-time prices create gaps. The dispersion measure is max(d)−min(d) across bookmakers with the same known period, settlement, outcome, line, market, event and timestamp. No interpolation is used for comparisons. Historical snapshots from different source identities remain separate.

Event IDs are scoped to source and origin. Without a provider ID the fallback uses normalized Unicode, whitespace and case for the ordered participants, competition, season and date. An ambiguous fallback or conflicting identity withholds linkage. Explicit aliases in the cross-provider comparison view produce review candidates. Time-series charts do not merge them automatically.

For three outcomes, multiclass Brier = mean Σ(pᵢ−yᵢ)², without division by the number of classes. Log loss = mean −ln(p_observed). The training prior for outcome i is (countᵢ+1)/(N+3). Accuracy uses the most probable class. Calibration gaps are predicted share minus observed share per outcome per holdout. The uniform model assigns 1/3 to each outcome. Scores are retrospective. The immutable April 2021 training snapshot predates every holdout fixture. No bookmaker prices or future results enter training.

## Installation from source and recovery

On Windows with x64 Python 3.13 and Tk, create a virtual environment, install `requirements.txt`, then run `python application/living_launch.py`. For service mode use `--serve --mode offline --port 0 --data-dir PATH`. For an interactive dashboard, use the native launcher's Start control. Use a separate data directory for a new release trial. Fresh installs begin with no credentials or private datasets.

Before changing releases, stop the application gracefully and use Recovery to create a backup. A failed backup integrity check aborts index creation. To restore an earlier release, open its launcher with a separate directory and restore the pre-upgrade backup there. Protected credentials are scoped to the user and directory and may require re-entry. Retain source originals and settings alongside regular backups. For PostgreSQL use the dedicated backup and fresh-schema restore workflow. Tests and package acceptance use disposable directories and isolated installer registration.
