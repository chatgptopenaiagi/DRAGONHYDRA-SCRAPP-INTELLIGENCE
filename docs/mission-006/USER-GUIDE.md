# DRAGONHYDRA Intelligence 0.2.0-beta.3

Open DragonhydraIntelligence.exe. The native launcher reopens an authenticated dashboard for its selected data directory. Port 0 chooses a free port; another database is never silently reused. Default state is in %LOCALAPPDATA%/DRAGONHYDRA/LivingIntelligence, outside the program directory. Closing the launcher leaves the service running; use Stop gracefully.

## Football
Six independent adapters remain available. API-Football has a dedicated Test authentication / account quota action using /status. Discover competitions separately, choose a supported season and bounded date range, save configuration and Collect now. Each operation creates a receipt. Imported football results, historical odds and synthetic records remain distinguishable. No live odds access is implied. Free coverage is determined by your actual account. Scheduling is opt-in.

## CSV
Import Data → choose CSV → preview → create/select source → inspect column dropdowns → validate → confirm. Inspect actual accepted, rejected and duplicate counts. Open records and analyze. The owner-supplied Champions League file is private and is not included in the distribution.

## Cloud and local AI
Open Cloud AI Control Center. Configure an official provider origin, enable it, save your credential and Test connection. A model catalog is not proof that every model accepts every request; select a compatible text model actually available to your account. Azure requires your deployment name. All cloud providers are initially disabled. Local compatible servers use an explicit loopback origin and remain usable offline.

Select up to 20 observation IDs and 5 retrieved knowledge sources. Preview the exact redacted payload, then approve sending it. The preview expires after five minutes and can be used once. Requests have byte, timeout, output and daily-count limits, but do not establish an exact monetary cap. Actual provider usage is recorded when supplied. No inference request is automatically retried after interruption. Interpretations are retained separately and never overwrite observations.

Manus uses asynchronous tasks and account credit/task pricing, not a chat model token budget. Tasks explicitly disable inherited connectors; progress and stop operations are deliberate. Copilot Studio uses a configured Direct Line agent, not a consumer Copilot subscription. Its agent-side actions are governed by that agent configuration. No automatic action confirmation is sent by DRAGONHYDRA.

## Credentials and backups
Keys use Windows user-scoped DPAPI, bound to the dataset path and provider origin. Saved keys are never returned to the dashboard. New key inputs clear after saving. SQLite backups exclude the private credential directory, so portable packages and ordinary data exports contain no saved credentials. Restoring on another user account or moving the dataset requires credential re-entry. Removing a key disables that provider locally; revoke at its official account dashboard if needed.

## SQL
SQLite remains available. SQL Server Control Center discovers local registry configuration and ODBC drivers without claiming a successful SQL login. Select the actual server, an installed driver and existing maintenance guard. A blocked guard prevents connections and writes. No UI operation releases it. Integrated authentication and normal SQL permissions are required. Provisioning is limited to explicitly confirmed DRAGONHYDRA_M006_ databases with a database ownership marker. Transactions preserve original observation IDs and fingerprints. Synchronize in bounded pages; repeating a page checks duplicates. SQL backup catalog entries are not proof of a restorable backup.

## Living Search and evidence tools
Search the saved official-source registry. Enable a selected URL and refresh it to retain content, hash and retrieval time. Redirects require review. Daily refresh is opt-in. This bounded registry does not crawl arbitrary sites or turn documentation into observed football data. The eleven read-only evidence tools accept structured filters and approved SQL templates only.

## Limitations
SQL live acceptance requires a released guard and authorized integrated login. Cloud providers require independently authorized API credentials and usable account allowances. Mock protocol acceptance is not live provider verification. Microsoft Foundry Model Inference is a documented deprecated preview interface; Azure OpenAI Responses is separately supported. Joomla site acceptance and unrelated local AI engines are not certified by this release. Consult release acceptance reports for the exact executed results.
