# DRAGONHYDRA SCRAPP INTELLIGENCE

Windows beta 0.2.0-beta.1: local evidence storage, bounded imports, reproducible numerical analysis and an authenticated dashboard.

Download the portable ZIP, extract it and open DragonhydraIntelligence.exe, or use the per-user Windows installer. Select Start / open dashboard in the native launcher. Application data lives outside the installation in the current user's local application data directory. New installations start empty; private historical datasets and synthetic demos are not bundled.

The application supports CSV, TSV, JSON, JSONL, XLSX, structured XML, a single HTML table, text PDF and read-only SQLite sources. Approved public HTTP endpoints require connected mode. Every record carries source and provenance information. Derived analyses retain inputs, methods and uncertainty. Recovery center provides task receipts, interrupted-task resume and verified backups.

See [the user guide](docs/mission-004/USER-GUIDE.md), [architecture](docs/mission-004/ARCHITECTURE.md), [contracts](docs/mission-004/MODULE-CONTRACTS.md), [provenance](docs/mission-004/DATA-PROVENANCE.md) and [security](docs/mission-004/SECURITY.md).

SQL integration is BLOCKED pending authorized maintenance and acceptance. The isolated Joomla bridge is staged; actual Joomla-site integration is BLOCKED until installation and end-to-end verification. Live bookmaker access, current weather feeds and real AI model integration are not claimed. Local AI is optional and disabled by default; cloud providers are disabled. This unsigned beta is not production certification.

For source development use Python 3.12 or newer in an isolated environment, install requirements.txt, then run `python application/living_launch.py`. Run the behavioral suite with `python -m unittest discover -s tests -p test_mission004.py -v`. Windows packaging uses requirements-build.txt and `python tools/build_windows.py`. No system-wide Conda installation is required for the distributed application.

Source publication does not include private datasets, original research archives, credentials or machine-specific recovery evidence. Third-party runtime notices are included with binary distributions. No license to third-party datasets is granted by this repository.
