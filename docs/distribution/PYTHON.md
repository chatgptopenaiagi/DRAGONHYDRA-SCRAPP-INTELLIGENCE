# DRAGONHYDRA Intelligence for Python

Install the downloaded wheel with Python 3.12 or later.

    python -m pip install ./dragonhydra_intelligence-0.3.0b1-py3-none-any.whl
    dragonhydra --version
    dragonhydra calculator 5/2 --format fractional
    dragonhydra dashboard
    python -m dragonhydra_intelligence --help

The default dashboard runs offline on loopback and opens an authenticated browser session. The --data-dir option selects a separate SQLite profile. Use dashboard --stop with the same profile to stop it. Core analysis uses the Python standard library. Install the optional workstation extra for PDF, process, WebSocket, PostgreSQL and Windows ODBC integrations.

    from dragonhydra_intelligence import odds, evaluate_binary, market_csv
    single = odds.analyze_decimal("2.50")
    report = odds.calculate_market({"market": "two-way", "format": "decimal",
        "prices": {"first": "2.50", "second": "1.60"},
        "assumption": {"outcome": "first", "probability": "0.45", "basis": "User scenario"}})
    print(single["implied"], report["expected_value"]["net_per_unit"])
    print(market_csv(report))
    print(evaluate_binary([0.7, 0.2], [1, 0])["brier"])

The JSON input to analyze and export uses the same market object as calculate_market. Run dragonhydra analyze market.json or dragonhydra export market.json results.csv. For structured JSON use results.json. Output preserves the supplied scenario. Market math assumes exhaustive outcomes and proportional normalization. EV is net return per unit under the named probability assumption.

The public package also exports parse_scoreboard(payload, league) for ESPN event responses, normalize_observation(raw, source, origin, collected) for source records with raw hashes and original clocks, historical_market(quotes) for one source-owned event's workstation quote views, and Store(path) for an owned SQLite database. Binary evaluation returns Brier score and mean log loss using the workstation's 1e-15 logarithm floor. Packaged backtest evidence is available through importlib.resources.files("living").joinpath("web/backtest.json"). API records are JSON-serializable except that odds.to_decimal and odds.implied_probability return Decimal. Never treat proportional market probabilities as calibrated outcome estimates.
