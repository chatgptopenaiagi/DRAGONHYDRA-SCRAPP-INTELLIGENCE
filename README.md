# DRAGONHYDRA SCRAPP INTELLIGENCE

Mission 006 candidate **0.2.0-beta.3** adds a five-company AI conversation cockpit to the Windows intelligence application. This local candidate passed packaged read-only SQL, cockpit and installer acceptance. **Public release is held:** OpenAI key authentication passed, but the authorized account has no API credits for the required genuine conversation test. Previous public beta.1 and beta.2 remain unchanged.

The portable executable and per-user installer include their runtime. Open DragonhydraIntelligence.exe, select a dedicated candidate data directory and free port, then Start / open dashboard. A newer launcher refuses to silently reuse an older running service. Original user data, releases and source evidence are preserved. Credentials and private datasets are not included in packages.

## Working workflows

CSV import previews the actual file, creates a source, maps columns, validates records and commits atomically. Six football providers have independent configuration, protected credentials, budgets and receipts. API-Football authentication and bounded historical collection have passed live acceptance. Historical football results, bookmaker prices, synthetic observations and AI interpretations remain distinct.

AI Intelligence Cockpit offers OpenAI Responses, Claude Messages, xAI Responses, Microsoft developer interfaces and Manus tasks. Local compatible inference remains optional. Each conversation retains its own provider, endpoint, model, messages, usage and tool receipts. Floating chat can move, resize, dock, expand and minimize across dashboard views. Roundtable explicitly sends separate requests to selected companies and displays their independently identified replies. No fake company replies are generated when access is unavailable.

The tool registry exposes bounded football and SQL queries, diagnostics and measured hardware readings. Data-changing requests become owner actions. The existing SQL maintenance guard is checked before any connection. Codex engineering attaches an existing authorized App Server thread and has passed an actual diagnostic through that worker; it does not create another Codex session or grant cloud models shell execution. Optional local read-only MCP uses a separate scoped credential on the existing loopback server.

## Verified limits

OpenAI inference is BLOCKED by account credit exhaustion. Claude, xAI, Microsoft and Manus have mock protocol acceptance only until authorized credentials and account access are configured. Mock replies are not live cloud verification. Owner-approved read-only SQL connection, version, identity and catalog queries passed live acceptance. Application-database access remains restricted by the Windows login; SQL writes remain blocked. Joomla live acceptance remains incomplete. Remote MCP execution and direct import of ChatGPT account plugins are not implemented. Manus and Copilot Studio use real task/channel lifecycles but do not have a verified local function-call interface in this beta; owner-selected tool receipts provide bounded context. CPU temperature and per-process network attribution are marked unavailable when no verified sensor exists.

Conversation and credential security, bounded tools, cancellation, restart persistence, actual Edge interactions and installer lifecycle have local acceptance evidence. No purchase, subscription or automatic paid retry is performed. User-defined request limits are application-local, not account-wide billing caps. This is a beta candidate, not production certification.

Read [read-only SQL operation](docs/mission-006/SQL-READONLY.md), [AI cockpit operation and limits](docs/mission-006/AI-COCKPIT.md), [Mission 006 user guide](docs/mission-006/USER-GUIDE.md), [module contracts](docs/mission-006/ARCHITECTURE.md) and [football provider documentation](docs/mission-005/FOOTBALL-API-COST-COMPARISON.md).

## Development

Use an isolated Python 3.12+ environment and requirements.txt; ordinary Windows use needs no developer interpreter. Run `python -m unittest discover -s tests -p "test_mission*.py" -v`. DPAPI tests require Windows. `python tests/mission006_cockpit_browser.py --exe PATH_TO_EXE` exercises actual Edge controls with synthetic provider fixtures and must be reported MOCK_PASS. No owner keys belong in tests or source. Build with the existing PyInstaller toolchain using `python tools/build_windows.py --mission 006 --version 0.2.0-beta.3`. Keep local evidence, private databases, DOCX credentials and DPAPI files out of publication.
