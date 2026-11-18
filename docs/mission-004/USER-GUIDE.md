# Using DRAGONHYDRA Intelligence

Open DragonhydraIntelligence.exe. The native launcher shows whether your selected dataset is running. Choose Offline or Configured connections and Start / open dashboard. The application checks database integrity and opens a short-lived authenticated browser exchange automatically. If a browser session expires, reopen it from the launcher. Closing the launcher does not stop acquisition; use Stop gracefully.

The default dataset is in your local application data folder, outside the application installation. Portable software therefore works from removable or read-only program locations. A new dataset is empty. It does not invent demonstration observations.

In Data sources, choose a unique source ID and acquisition method. Upload CSV, TSV, JSON, JSONL, XLSX, structured XML, a single HTML table or a text-based PDF. Configure SQLite through a read-only table source. Map destination names such as value, key, unit and observed_at to your file's columns. Observation timestamps require explicit offsets. For PDF, text is extracted as text records; no OCR is performed. XLSX defaults to sheet1; use reader options for another sheet. Inspect every import's receipt in Recovery center. Invalid batches commit no rows.

Use the Football Universe adapter only with its owned schema-1 database. It imports historical results and selected recorded Bet365 prices into this candidate while leaving the source unchanged. Historical match dates are not precise quote timestamps. Imported values never become verified live data. The legacy SCRAPP adapter preserves the original synthetic classification.

Select a source, series and provenance class before Analyze. Results include descriptive statistics, moving averages, a distribution, dispersion, change and review outliers. Inspect the inputs, algorithm version, dataset fingerprint and assumptions. Correlation requires at least three exact known observation-time pairs. Saved analyses are retained separately from original evidence. CSV and JSON exports are bounded to 10,000 rows per query; narrow the filters or use query pagination for larger sets.

Configure connected HTTP sources only with permission. The source must use a public HTTP(S) address; local/private endpoints are rejected for acquisition. Offline mode blocks external requests. Local AI is configured separately under Diagnostics, is disabled by default, receives at most 50 scoped records and cannot edit measurements. Cloud AI is disabled.

Recovery center shows tasks, interrupted operations and backups. Resume retains original staged bytes and does not repeat a committed import. Restore from the native launcher only after the candidate stops; the current dataset is backed up first. Startup crash records and structured events remain in the data directory. SQL and actual Joomla integration remain separately blocked; their status does not prevent local analysis.

The installer operates per user. Upgrades preserve user data and the previous program directory for rollback. Uninstall removes only owned application files and registration; it never deletes your data. The portable edition can always be kept separately as a rollback copy. This is an unsigned beta candidate, not production certification.
