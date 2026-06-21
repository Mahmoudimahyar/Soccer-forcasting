# Data Source and Scraping Governance

## API adapters

The project provides read-only adapters for:

```text
API-Football: fixtures, results, lineups, events, statistics, standings
The Odds API: pre-match market snapshots
Open-Meteo: venue forecast features
Kalshi: market data and guarded exchange access
```

No key is embedded in source code. Keys live in `.env` or a production secret manager.

## Adding a new source

Claude Code must create `data_requests/pending/<source_id>.yaml` from the template and
ask the user to approve it before adding code. The request must explain the incremental
signal, terms, cost/account requirement, rate limits, latency, historical coverage,
leakage control, raw snapshot plan, normalized schema, and tests.

## Scraping

The built-in fetcher is intentionally restrictive:

```text
- allowlisted domains only
- public pages only
- robots.txt respected
- rate limited and cached
- no login, paywall, CAPTCHA, or anti-bot bypass
- raw source URL and retrieval time retained
```

The agent may not turn "scrape any information" into unrestricted crawling. A source that
is legally, technically, or methodologically fragile can make the model less reliable.
Use sanctioned APIs and open datasets for core runtime data; use narrowly approved public
scraping only as a supplemental input.

## Data quality hierarchy

1. Official event/result and exchange data
2. Licensed/sanctioned API data
3. Reproducible open historical datasets
4. Approved public official announcements
5. Never use unsourced rumors as automated model inputs
