# DRAGONHYDRA Intelligence on Android

Download the universal APK from v0.3.0-beta.1, open the file and use the Android package installer. Android may ask you to allow installations from the browser or file manager you used. You can turn that permission off after installing. The app requests zero manifest permissions and runs without an account. It uses the device's Android System WebView to render bundled resources.

**Compatibility.** Minimum API 26 (Android 8), target API 36. Use an up-to-date Android System WebView. The APK contains Dalvik bytecode and bundled web assets, with no ABI-specific libraries. The release acceptance device was an x86_64 Android 37 emulator. ARM phones, physical tablets and the minimum Android version have not been device-tested.

**Overview.** Inspect English Premier League and German Bundesliga results across eight holdout league seasons. The source drawers identify the pinned league files and checksums. These are archived model scores. Choose a light, dark or system theme.

**Calculator.** Choose two-way or 1X2, then enter decimal, American or positive fractional odds. To evaluate expected value, select the outcome and supply a probability and its basis. The Java engine uses 34 significant decimal digits and half-even rounding. Model scores, market-implied weights and user assumptions have separate labels.

**History.** Open History and choose Import JSON. Select a DRAGONHYDRA mobile ledger with the Android document picker. Search by event, source or outcome. Select a series to see observation times, quoted decimal odds and their movement. Equal-time price conflicts stay visible and interrupt the chart line. Use Export JSON to create a restorable copy and Export CSV for analysis. A fresh installation starts with an empty ledger. Uninstalling removes the app-private database and preferences.

The ledger records full-time match winner selections only. Give each event and source an unambiguous identifier. Use an ISO 8601 observation time with an explicit offset. Imported documents do not establish that a source or price has been independently verified. The canonical UTC time retains up to nine fractional digits. Identical records deduplicate. Conflicting records are preserved. Imports are atomic and limited to 4 MiB and a total of 2,000 stored observations.

    {
      "schema": "dh.mobile-history/1",
      "market": "full-time match winner",
      "observations": [{
        "event": "Synthetic exhibition A v B",
        "source": "Synthetic example",
        "selection": "A",
        "at": "2026-01-01T10:00:00Z",
        "decimal": "2.10"
      }]
    }

[Downloadable synthetic ledger](../../android/test/assets/fixture.json). Android provides archived football research, local quote histories and market calculations. Online provider collection, PostgreSQL, desktop source management and AI integrations remain workstation features.
