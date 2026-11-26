# DRAGONHYDRA Next Generation 0.3.0-beta.1

**Autonomous Sports Intelligence and Mathematical Odds Analysis Platform** · Windows x64 prerelease · 26 November 2026

Download the portable ZIP to run from an extracted directory or the installer EXE for a per-user installation. Both include the same application. The source ZIP contains the versioned application, tests, guides and backtest. SHA256SUMS.txt covers the downloadable assets. For first use, open DragonhydraIntelligence.exe, choose a data directory and select **Start / open dashboard**. The app starts offline by default.

## What changed

The sports desk collects and retains ESPN scoreboards for five leagues, with source receipts, observation IDs, original capture time and membership in the latest successful snapshot. Historical market tools match quotes to source-owned events, withhold ambiguous links, distinguish missing clocks and chart comparable bookmaker series. The calculator handles decimal, fractional and American markets, overround, proportional normalization, theoretical margin, fair decimal prices and expected value under a supplied assumption.

The release carries forward the unpublished beta.5 local application, including optional PostgreSQL and beginner guidance. It fixes the regression harness left behind when the application switched its primary SQL integration to PostgreSQL. The preserved SQL Server adapter now has direct isolated tests. No observed source data was deleted.

## Discovery and preservation

The public SCRAPP INTELLIGENCE beta.2 tag and main branch were at `db58b3c4a50593e651cb32d16ea7ce693464c114`. The clean local Mission 006 worktree on `mission006-beta3` had advanced to `5f8eee24040071b245cf463e2c128cc39660a238` with verified beta.5 packages. The release branch starts from this descendant. The older DRAGONHYDRA and CORE NEXT repositories contain GENESIS/Windows/Joomla/Android tracks. Their source and services are independent. DRAGONHYDRACHILD is an earlier research fork. The local Odds Mirror is a packaged research application, and Football Data Universe contains historical SQLite sports data. The separate DRAGON football engine and Field Intelligence Console have independent histories.

A read-only SQLite online backup of the 3,341-observation Mission 005 archive supplied the working copy. Its original observations, the pre-index backup and the indexed copy had equal ordered payload digests and passed integrity checks. The release omits all private observations. The source in the existing worktrees, earlier releases and installed profiles remain recoverable. A release trial can use a new directory. Restore the pre-index or pre-migration backup in another directory to return to the prior release.

## Executed tests

| Check | Result |
|---|---|
| Original beta.5 unittest discovery with PostgreSQL dependency present | 136 discovered, 126 passed, 9 errors on a stale SQL Server test setup, 1 private CSV skipped. The first environment also lacked psycopg and reported a tenth error. |
| Final unittest discovery | 148 discovered, 147 passed, zero errors or failures, 1 private CSV skipped |
| Local source browser, extracted ZIP and installed EXE | 14 checks per run, including authenticated API access, offline scoreboard, actual JSON download, model display, optional AI failure, movement chart and mobile layout |
| Windows distribution | 1,743 manifest entries verified in the extracted ZIP and installed tree. Both native launchers opened and closed. Isolated install, upgrade, uninstall and user-data preservation passed. |
| PostgreSQL 18.6 | A disposable cluster passed provisioning, empty SQLite migration, activation, synthetic scoreboard receipt replay, provider quote foreign-key linkage and research projection. The cluster was stopped. |
| Backtest | 686 training matches, 2,744 held-out fixtures, four seasons each in the Premier League and Bundesliga |
| Recovery | A pre-index SQLite backup reopened with intact observations, integrity and the original schema. The supported launcher restore path reproduced all 3,341 original payloads in a separate directory. Regression discovery includes rollback and interrupted-operation tests. |

One intermediate run exposed a race in an inherited cancellation test that relied on a 100 ms sleep. The mock now signals receipt and holds its response until the test cancels the request.

Synthetic fixtures exercised event linkage, timestamp gaps, suspension, conflicts, two-bookmaker comparisons, exact-rational formula checks and failed local inference. Real ESPN historical imports separately yielded NBA 8, NHL 13, MLB 15, NFL 14 and Premier League 10 events. TheSportsDB and OpenLigaDB separately returned 10 and 44 competition records through their application adapters. These receipts establish event or competition data only. No live odds claims are made. The initial Premier League request failed at transport and a different documented scoreboard date succeeded.

## Performance and model results

On the same Windows workstation and 3,341-observation backup, a warm 25-row history read fell from **35.613 ms to 0.487 ms** median over 31 reads per version. A 25-match football research page fell from **375.082 ms to 299.061 ms** median over 11 reads per version. Use tools/benchmark_history.py with the same archive, source and two checkout paths to repeat the workload. The tests measure warm local reads and include decoding. Accepted packaged service startup took 0.817 s from the ZIP and 0.915 s from the installation in individual same-host runs. Four alternating fresh, empty source-process launches per revision had median startup 0.675 s before and 0.682 s after the change. Median working sets at first authenticated status were 30.15 and 30.2 MiB respectively. These are warm same-host measurements.

The league-frequency prior scored **0.64854 multiclass Brier and 1.07152 log loss**, versus **0.66667 and 1.09861** for equal probabilities. It scored better on both metrics in all eight league-season partitions. The 2019–20 training bytes were committed in April 2021. All validation dates are later. A league-wide constant prior cannot distinguish individual fixtures. These results do not establish a predictive edge against bookmakers.

## Known limits

- The 2,280 prices in the historical football archive have no exact quote timestamps. They can be inspected and converted. They cannot establish intraday movement or synchronized provider spreads. Synthetic timestamped fixtures supplied chart and suspension acceptance.
- Football research currently requires a selected scope of at most 10,000 observations. ESPN scoreboard snapshots use a separate event contract. Derived football histories are confined to one source and provenance class. Cross-source matches remain review candidates.
- Four keyed football adapters were not live-tested with credentials in this release. The dashboard retains their configuration, documented limitations and earlier mock tests. No paid requests or wager placement occurred.
- Optional loopback AI supports evidence explanations. Disabled and unreachable states were tested. This release does not certify an installed language model, cloud inference, an active Joomla site or an Android client.
- Binaries are unsigned. Windows x64 is the only packaged platform. Installer checks used isolated per-user registration, alongside earlier installations. The private CSV test requires DH_ACCEPTANCE_CSV. Developer benchmarks and packaged tests used disposable state.

[Machine-readable verification](VERIFICATION-0.3.0-beta.1.json) · [User guide, architecture, formulas and recovery](next-generation/PLATFORM.md) · [Research roadmap](next-generation/ROADMAP.md)
