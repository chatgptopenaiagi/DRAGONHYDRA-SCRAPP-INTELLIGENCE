# DRAGONHYDRA 0.2.0-beta.1 architecture

The 0.1.0 executable, port 18975 and original SQLite database remain a separate running rollback candidate. Mission 004 adds the `application/living` package and a separate dataset/port. It reuses the existing public-address-pinned HTTP transport and byte-preserved CORE probability mathematics; it does not replace unrelated installations.

The composition root creates one SQLite store, one acquisition worker, one loopback HTTP server and a native launcher. Modules communicate through explicit dictionaries described in MODULE-CONTRACTS.md. Domain functions do not know about the HTTP server. The database never imports the user interface.

| Module | Implementation / responsibility |
|---|---|
| DH-CORE | contracts.py, core.py; lifecycle, registry, structured events |
| DH-NORMALIZATION | normalization.py; explicit clocks, types, identity, units, trust |
| DH-STORAGE | storage.py; owned schema, immutable observations, atomic imports, backups |
| DH-ACQUISITION | acquisition.py; bounded readers, staging, queue, cancellation, scheduling |
| DH-ANALYTICS | analytics.py; documented descriptive statistics, distributions, change, correlation, binary prediction evaluation |
| DH-SPORTS | connectors.py and analytics.odds; historical football and retained CORE mathematics |
| DH-SENTIMENT | analytics.sentiment; limited English lexicon with abstention |
| DH-WEATHER | normalization.py and weather UI; distinct measurement/forecast clocks |
| DH-DIAGNOSTICS | core.status, database events, startup crash reports |
| DH-CONNECTORS | connectors.py; read-only football/legacy data, guard-first SQL, optional local AI |
| DH-UI | launcher.py, server.py and web assets; native launch/control and authenticated analysis |

SQLite is the default working store in both offline and configured connected mode. Connected mode permits only independently approved sources; it does not assert SQL availability. The SQL adapter remains guarded and is not production-qualified. Joomla is an optional isolated bridge requiring actual installation/communication acceptance. ARX and optional AI engines are interfaces, not claims of completed integration.

One OS file lock owns each candidate dataset, across process crashes. SQLite FULL synchronous WAL and atomic import receipts prevent partially committed batches. Startup marks interrupted tasks for explicit review; staged source bytes allow retry. No upstream research program is executed. Read-only integration data and personal historical odds are excluded from public packages.

Default writable state is `%LOCALAPPDATA%/DRAGONHYDRA/LivingIntelligence`, independent of executable location. `--data-dir` selects an explicit workspace. Installations are per user and contain no data by default. The installer uses its owned file manifest, preserves user data across upgrades/uninstall, and refuses an unowned target.
