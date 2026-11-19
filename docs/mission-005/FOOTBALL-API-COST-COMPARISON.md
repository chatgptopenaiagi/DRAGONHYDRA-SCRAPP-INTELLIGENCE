# Free football sources — verified 19 November 2026

All six connectors start disabled. Mandatory monthly subscription cost is **€0**. No paid enrollment or request was authorized. Advertised availability and executed access are separate evidence.

| Provider | Documented free access | Authentication | Paid entry reference | Important limit |
|---|---|---|---|---|
| APIfootball.com | 180 calls/hour/endpoint; England Championship and France Ligue 2; fixtures, results, standings and advertised 1X2/BTS/O-U/AH odds | APIkey query parameter | European $21/month | Keyed live access and odds remain unverified |
| API-Football / API-Sports | 100 requests/day; all endpoints advertised, restricted seasons | x-apisports-key header | Pro $16/month, excluding VAT | Coverage varies by competition and season |
| TheSportsDB | Public v1 key 123; 30 requests/minute; endpoint record caps | Public key in v1 server-side path | $9/month dedicated key/v2 | Free whole-season completeness and live scores cannot be assumed |
| Highlightly | Basic 100 requests/day; fixtures/scores/standings and other documented football data | x-rapidapi-key, direct Highlightly host | Pro $9.49/month | Free plan excludes odds; some results can be hidden |
| football-data.org | 12 competitions; delayed scores and schedules; tables; 10 calls/minute | X-Auth-Token header | Live-score entry €12/month | Deep history is plan-dependent |
| OpenLigaDB | Public community data, no key; 60 requests/minute/IP | None | No mandatory subscription documented | ODbL attribution/share-alike conditions; cache and poll sparingly |

Sources: [APIfootball pricing](https://apifootball.com/), [APIfootball documentation](https://apifootball.com/documentation/), [API-Football pricing](https://www.api-football.com/pricing/), [API-Football documentation](https://www.api-football.com/documentation-v3), [TheSportsDB documentation](https://www.thesportsdb.com/documentation), [TheSportsDB API overview](https://www.thesportsdb.com/API.php), [Highlightly pricing](https://highlightly.net/football-api/), [Highlightly limits](https://highlightly.net/football-api/documentation/getting-started/pagination/), [football-data pricing](https://www.football-data.org/pricing), [football-data policies](https://docs.football-data.org/general/v4/policies.html), [OpenLigaDB schema](https://api.openligadb.de/swagger/v1/swagger.json), [OpenLigaDB terms](https://www.openligadb.de/en/terms-of-use).

OpenLigaDB asks larger distributed applications to collect centrally and serve their own cache. This beta defaults to manual collection and a conservative local cap; it does not provide a public aggregation service. Users must respect the provider's usage and data-license terms. It does not fetch or redistribute team images. [OpenLigaDB terms](https://www.openligadb.de/en/terms-of-use)

Football Charts remains an optional seventh research candidate, without an enabled adapter. Its current developer page advertises 25 REST requests/day without a key, 200/day with a confirmed free key, current/previous seasons and personal-use restrictions. It provides predictions and results, not bookmaker odds. Personal is €9/month until November 30, with €19 announced for new subscriptions from December 1, 2026; commercial use has separate terms. REST and MCP use are documented, including Bearer authentication. No account was created or plan purchased. [Official developer information](https://www.football-charts.com/developers)

Football-Data.co.uk remains a historical CSV source. Its bookmaker columns distinguish pre-closing and closing prices; the C marker denotes closing values in recent files. It is not represented as one of the required live APIs. [CSV downloads and notes](https://football-data.co.uk/downloadm.php), [field definitions](https://football-data.co.uk/notes.txt).

The application applies conservative local budgets in addition to documented account limits. Local counters cannot reveal calls made by other programs. Review the provider account and response headers for actual remaining entitlement. All pricing and limits can change after this verification date.
