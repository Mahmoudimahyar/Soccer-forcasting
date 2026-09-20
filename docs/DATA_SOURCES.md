# Data sources, licences and attribution

This page lists the third-party data sources the lab used or evaluated, the terms each is offered under,
what (if anything) derived from it is tracked in this repository, and how it is credited. If you find a
source that is missing, please open an issue.

Licence facts were checked against the upstream pages on **2026-09-20**. Terms change; the upstream page
always wins. Where a term could not be confirmed, this page says "licence not verified - check upstream"
instead of guessing. Nothing here is legal advice.

Model names (B1, B2) and terms such as leave-one-competition-out are defined in
[`GLOSSARY.md`](GLOSSARY.md).

Contents: [1. The principle](#1-the-principle) ·
[2. Source table](#2-source-table) ·
[3. Attribution lines](#3-attribution-lines) ·
[4. Non-commercial note](#4-non-commercial-note) ·
[5. Getting the data yourself](#5-getting-the-data-yourself) ·
[6. Known inaccuracies in the provenance ledger](#6-known-inaccuracies-in-the-provenance-ledger)

---

## 1. The principle

**The [MIT licence](../LICENSE) covers the code and the author's own writing. It does not cover, and
cannot re-license, anyone else's data.** Every dataset below stays under its own upstream terms.

**No raw third-party payload is tracked in this repository.** The directories that hold provider data are
excluded by [`.gitignore`](../.gitignore):

| Ignored path | What lives there on the author's machine |
|---|---|
| `data/raw/` | Downloaded open datasets and verbatim API responses, including raw odds snapshots |
| `data/processed/` | Tables built from the raw data, including normalised odds snapshots (one metadata file is tracked on purpose, see below) |
| `data/cache/` | Provider response caches |
| `outputs/` | Runtime artefacts: the frozen shadow-prediction ledger, scorecards, collector state |

The StatsBomb event lake used by the in-play research lines sits outside the repository entirely, on the
author's disk. It is not published.

An internal audit on 2026-09-20 opened every tracked file under `data/` and `data_requests/` and searched
the history of all local branches. In those files it found no event rows, player tables, odds or price
series, commentary text, ranking tables or API response bodies. In the history it found no commit that
ever added a file under `data/raw/` or `outputs/`, a `.env` file, or a binary dataset. This was an
internal check, not a third-party review.

### What is tracked

| Kind | Examples | Why it is kept |
|---|---|---|
| Provenance metadata | [`data/processed/source_provenance.json`](../data/processed/source_provenance.json) (URL, licence string, byte size, SHA-256 of files that are *not* tracked), [`data/source_registry.json`](../data/source_registry.json) | So a reader can fetch the same bytes and check the hash |
| Identifier manifests | API-Football fixture-ID lists; StatsBomb match indexes in [`data/reference/`](../data/reference/) | So cohorts can be rebuilt exactly |
| Content hashes | SHA-256 per event file in the event-lake manifests | Integrity checks without shipping the content |
| Per-match aggregate counts | Number of events, shots, cards, substitutions; availability flags | Coverage audits |
| The lab's own ledgers | Model decision ledgers, cohort-exclusion ledgers, power analyses, prospective prediction manifests | These are the research record |
| Desk research about vendors | [`structured_event_provider_catalog.json`](../data/reference/structured_event_provider_catalog.json), [`commentary_source_catalog.json`](../data/reference/commentary_source_catalog.json) | Compiled from public pages in June 2026; not endorsed by or affiliated with any vendor; verify before relying on it |
| Synthetic or demo files | `data/seed/sample_odds_2026.csv` (every row labelled as generated demo odds, not real prices), `data/seed/seed_ratings_2026.csv` (labelled approximate/demo) | Lets the toolkit run without any account |

### Tracked files that carry match facts, not only identifiers

These are described plainly so nobody has to discover them:

- `data/reference/official_modern_international_catalog.*` (333 rows) and
  `data/reference/statsbomb_event_process_catalog.*` (2,651 rows) are **match indexes taken from StatsBomb
  Open Data's match listings**: match id, competition, season, date, team names and, in the first file,
  the final score, stage and a source URL. They hold no event rows, coordinates, player data or xG values.
- The cohort, bridge and lineage ledgers built on top of those indexes (for example
  `international_event_lake_cohort_manifest.*`, `expanded_international_bridge_manifest.*`,
  `residual_58_match_cohort.csv`) carry StatsBomb match ids, team names or ids, and the lab's own
  regulation-time result labels.
- `data/reference/future_2026_prospective_queue.csv` (72 rows) holds the 2026 group-stage fixture list from
  API-Football (fixture id, team names, kickoff time, status) next to the lab's own Elo-based anchor
  probabilities. It holds no scores and no odds.
- `data/seed/worldcup_2026_seed_matches.csv` (29 rows) holds 2026 fixtures and early results with a
  per-row press citation (Reuters, SBNation, The Guardian, 18 June 2026).

**Open item - StatsBomb match indexes.** Clause 1.2.1 of the StatsBomb user agreement bars reproducing or
distributing "the data". The files above copy match-listing fields only, with attribution, and an internal
audit rated them low-risk. That is the lab's reading, not a legal judgement. Whether to trim them to
identifiers only is a decision for the maintainer.

The index of `data/reference/` is in [`data/reference/README.md`](../data/reference/README.md). Some
manifests there are point-in-time snapshots that disagree with the current coverage ledger; see
[ERRATA E7](ERRATA.md).

**If you are a rights holder** and think a tracked file goes further than it should, please
[open an issue](https://github.com/Mahmoudimahyar/Soccer-forcasting/issues). The file will be reviewed and,
if needed, removed.

---

## 2. Source table

"Tracked here" means committed to this repository. "Nothing" means only a URL, a licence string and a
file hash appear, in the provenance ledger.

### Open datasets

| Source | What the lab used it for | Licence / terms (checked 2026-09-20) | Tracked here | Attribution |
|---|---|---|---|---|
| [martj42/international_results](https://github.com/martj42/international_results) | Men's international results since 1872: the input to the internal Elo ratings (B1), and a lagged fallback for 2026 results | **CC0 1.0 Universal** (upstream `LICENSE` file) | Nothing | Not required; credited as a courtesy |
| [Fjelstul World Cup Database](https://github.com/jfjelstul/worldcup) (`jfjelstul/worldcup`) | World Cup group structure and results 1998–2022; host lookup | **CC-BY-SA 4.0** (upstream README). The lab's provenance ledger wrongly records "MIT"; see [section 6](#6-known-inaccuracies-in-the-provenance-ledger) | Nothing | **Required.** See [section 3](#3-attribution-lines) |
| [StatsBomb Open Data](https://github.com/statsbomb/open-data) | In-play research: the 302-match men's international set (nested leave-one-competition-out rerun, xG feature tests); the 258-object content-addressed event lake (231 model-eligible matches); a 669-match club auxiliary index | **StatsBomb Public Data User Agreement** (upstream `LICENSE.pdf`, last updated 8 September 2023). Not a Creative Commons licence. Summary below the table | Match indexes (ids, dates, teams, scores), SHA-256 hashes, per-match aggregate counts and eligibility flags, the lab's cohort and decision ledgers. **No event data** | **Required.** See [section 3](#3-attribution-lines) |
| [SoccerNet-Echoes](https://huggingface.co/datasets/SoccerNet/SN-echoes) (`SoccerNet/SN-echoes`) | Commentary NLP side line (European club football, not World Cup): 383,591 ASR segments from 254 English-translated games | **CC BY 4.0** (Hugging Face dataset card) | Manifests with segment counts, precision figures and the SHA-256 of the (untracked) dataset file. **No commentary or ASR text** | **Required.** See [section 3](#3-attribution-lines) |
| SoccerNet action-spotting labels ([`Labels-v2.json`](https://github.com/SoccerNet/sn-spotting), via the official `SoccerNet` pip package) | Reference event labels (17 classes) for measuring the precision of commentary-derived events | **Licence not verified - check upstream.** Details below the table | Class counts and aggregate metrics only. **No label files** | Credited; cite the SoccerNet-v2 paper ([arXiv:2011.13367](https://arxiv.org/abs/2011.13367)) |
| [Dato-Futbol/fifa-ranking](https://github.com/Dato-Futbol/fifa-ranking) | Historical FIFA ranking: the B2 "FIFA-only" baseline, and ranking features that were tested and rejected | **No licence declared upstream.** The upstream README says the table was scraped from FIFA.com. With no licence, assume all rights reserved: local research use only | Nothing | Credited; no formal requirement found |
| [dcaribou/transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets) | Squad-value features on 128 Copa América / AFCON / Asian Cup games. Tested and rejected: 5-fold CV log-loss 0.834 with the features vs 0.813 Elo-only (worse) | Upstream repository `LICENSE` is **CC0 1.0 Universal**. Transfermarkt's own terms: **not verified - check upstream**. Details below the table | Nothing | Credited |

Notes on three of the rows:

- **StatsBomb.** In summary, the agreement provides the data for research and analysis; the data may not
  be distributed, reproduced or sold to third parties (clause 1.2.1); neither the data nor analysis
  derived from it may be commercially exploited (clause 1.2.2); published analysis must be accredited with
  the StatsBomb logo (clause 1.4).
- **SoccerNet labels.** No explicit licence statement for the label files was found. Upstream states that
  an NDA is needed for the *videos*; the label download needed no password. The pip package's code is MIT,
  which says nothing about the annotations. The lab treated the labels as non-commercial research data
  requiring attribution.
- **Transfermarkt.** The figures originate from Transfermarkt, and a licence on the scraper's repository
  does not settle Transfermarkt's own terms. The lab's ledger records "CC-BY-NC-SA", which could not be
  confirmed.

### Keyed and keyless APIs

| Source | What the lab used it for | Licence / terms (checked 2026-09-20) | Tracked here | Attribution |
|---|---|---|---|---|
| [football-data.org](https://www.football-data.org/) | 2026 World Cup group structure, fixtures and results; the verified-final results behind the prospective benchmark (35 of 35 fixtures verified final, 34 scored) | Football-Data.org General Terms and Conditions (on the site's About page). Attribution is section 7. A key applies to a single application, and section 6.1 bars storing keys in open-source repositories (none are stored here) | The lab's scoring ledgers and aggregate metrics. No API response | **Required.** See [section 3](#3-attribution-lines) |
| [The Odds API](https://the-odds-api.com/) | Pre-match bookmaker odds, used only as a read-only comparator: 2026 snapshots, the 2022 World Cup retrospective study (48 group matches), and 2021–2025 internationals in early exploratory notes (see [ERRATA E4](ERRATA.md)). Early-line caveat below the table | [Terms and conditions](https://the-odds-api.com/terms-and-conditions.html): storing the data and publishing values derived from it are permitted; offering it to others as a source of raw data is not | Snapshot counts, hashes and aggregate forecast-quality metrics. **No odds, prices or per-fixture market probabilities** | Not required by the terms; credited here |
| [API-Football](https://www.api-football.com/) (API-Sports, paid Pro plan) | Fixtures, events, lineups and team statistics for the international and club corpora; the score-reconciliation audits (900, later 1,120 fixtures) | Commercial API terms at `api-sports.io/terms`. **Licence not verified - check upstream**: the terms page refused automated retrieval (HTTP 403) on the check date. Treated as "no redistribution of payloads" | Fixture-ID manifests (provider fixture id, league id, season, kickoff time, status, pipeline state), the 72-row 2026 fixture queue (adds team names) and boolean coverage tables. **No response bodies, scores, events, lineups or player data** in those files | Credited |
| [Open-Meteo](https://open-meteo.com/) | A read-only adapter and a connectivity check. **No weather feature was added to any model**; no result in this repository depends on it | Data under **CC BY 4.0**; the free API is for [non-commercial use only](https://open-meteo.com/en/terms) | Nothing | Required if data is used. See [section 3](#3-attribution-lines) |
| Kalshi | A dormant, triple-gated paper/demo execution scaffold in `src/wcdrawlab/trading/`: never armed, never given credentials, no order ever placed | Exchange terms apply to anyone who creates an account. Not reviewed, because no account was used | Placeholder example files only (`EXAMPLE-MARKET`) | n/a |

> [!NOTE]
> **The market in the 2026 prospective benchmark is an early line, not a closing line.** For 31 of the 34
> scored fixtures the primary odds snapshot is a 2026-06-21 "baseline" snapshot (median about 98 hours
> before kickoff). The cause is a key mismatch that made the prediction freezer ignore all 47 snapshots
> taken by the durable collector ([ERRATA E2](ERRATA.md)). Read every comparison with the market in that
> light.

### Reference material

| Source | What the lab used it for | Terms | Tracked here |
|---|---|---|---|
| FIFA.com tie-breaker article, corroborated by press reports | The order of the 2026 group-stage tie-break rules (Article 13) | Facts, summarised in the lab's own words with source URLs. The official regulations PDF was not archived | [`data/reference/tiebreak_rules_2026.yaml`](../data/reference/tiebreak_rules_2026.yaml) |
| Wikipedia, "2026 FIFA World Cup" | Listed in the provenance ledger as a format reference | Text is CC BY-SA 4.0. No Wikipedia text is reproduced | Nothing |
| Press reports (Reuters, SBNation, The Guardian) | Early 2026 results in the seed file | Bare match facts with a per-row citation | `data/seed/worldcup_2026_seed_matches.csv` |
| Venue table | Approximate coordinates and altitude for 16 host stadiums | Hand-compiled public facts; no source is recorded in the file | `data/reference/venues_2026.csv` |

### Researched but never used

- **Paid event-data vendors.** Stats Perform / Opta, Sportmonks, Sportradar and StatsBomb's commercial
  tier were compared from public pages only. Nothing was purchased and no vendor was contacted.
- **SoccerReplay-1988** sits behind an NDA. The lab's acquisition report records it as blocked, and no
  download is recorded.
- **Official match centres and news live blogs** were ruled out for automated use on copyright and
  terms-of-service grounds. An Arabic live-text site listed in the commentary catalog was rejected as
  likely unlicensed.
- **FBref player minutes and a referee-history source** exist only as unexecuted requests under
  [`data_requests/pending/`](../data_requests/pending/). No code fetches them.

The policy is in [`COMMENTARY_DATA_LICENSING_POLICY.md`](COMMENTARY_DATA_LICENSING_POLICY.md) and
[`DATA_SOURCE_GOVERNANCE.md`](DATA_SOURCE_GOVERNANCE.md); the per-source rights matrix is
[`schemas/commentary_source_rights_v1.yaml`](../schemas/commentary_source_rights_v1.yaml).

---

## 3. Attribution lines

### StatsBomb Open Data

> Data provided by StatsBomb (https://statsbomb.com)

Upstream does not prescribe a sentence. Its README asks anyone who publishes research or analysis based
on the data to name StatsBomb as the source and to use the StatsBomb logo from its Media Pack; clause 1.4
of the user agreement makes the logo a requirement.

**Open item - logo.** This repository currently credits StatsBomb in text only. Adding the logo from the
official Media Pack, next to the in-play results that depend on this data, is a task for the maintainer.

The main tracked files derived from StatsBomb Open Data are `domain_event_process_inventory`,
`statsbomb_event_process_catalog`, `event_process_auxiliary_manifest`,
`international_event_lake_cohort_manifest`, `official_modern_international_catalog`,
`statsbomb_competition_catalog.csv` and `statsbomb_cache_audit.json`, all under `data/reference/`. The
bridge, lineage and cohort ledgers built on top of them reuse StatsBomb match ids and team names.

One reading note for those files: `reg_home_goals` and `reg_away_goals` in the cohort manifests are the
lab's clock-gated regulation-time values, not official final scores. In
`international_event_lake_cohort_manifest`, 51 of 258 rows differ and are flagged in the
`reconciliation_status` column (24 `mismatch_regulation_goals`, 27 `wdl_target_conflict`). The 27
conflicting rows are the ones excluded from the 231 model-eligible matches.

### SoccerNet-Echoes

> Data provided by SoccerNet (SN-echoes, CC BY 4.0)

Citation: Gautam, S., Sarkhoosh, M. H., Held, J., Midoglu, C., Cioppa, A., Giancola, S., Thambawita, V.,
Riegler, M. A., Halvorsen, P. and Shah, M. (2024). *SoccerNet-Echoes: A Soccer Game Audio Commentary
Dataset.* [arXiv:2405.07354](https://arxiv.org/abs/2405.07354).

Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Changes: none are distributed; this
repository publishes only counts and precision metrics computed from the dataset. The same attribution
string is recorded in
[`commentary_soccernet_sample_manifest.json`](../notes/research/commentary_soccernet_sample_manifest.json).

### Fjelstul World Cup Database

> Fjelstul, Joshua C. "The Fjelstul World Cup Database v.1.2.0." July 19, 2023.
> https://www.github.com/jfjelstul/worldcup

© 2023 Joshua C. Fjelstul, Ph.D. Licensed under
[CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). No table derived from this database is
tracked here. If you build one with these scripts and publish it, the share-alike condition applies to
your table.

### football-data.org

> Football data provided by the Football-Data.org API

### Open-Meteo

> Weather data by Open-Meteo.com

Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Listed for completeness: no
Open-Meteo data feeds any result here.

### Credited without a formal requirement

- International results: [martj42/international_results](https://github.com/martj42/international_results) (CC0).
- Odds: [The Odds API](https://the-odds-api.com/).
- Fixtures, events and lineups: [API-Football](https://www.api-football.com/).
- FIFA ranking history: [Dato-Futbol/fifa-ranking](https://github.com/Dato-Futbol/fifa-ranking), compiled from FIFA.com.
- Player valuations: [dcaribou/transfermarkt-datasets](https://github.com/dcaribou/transfermarkt-datasets), compiled from Transfermarkt.
- Action-spotting labels: SoccerNet-v2, [arXiv:2011.13367](https://arxiv.org/abs/2011.13367).

---

## 4. Non-commercial note

Several of these sources are offered for research or non-commercial use only:

- **StatsBomb Open Data** forbids commercial exploitation of the data *and of analysis derived from it*.
- **Open-Meteo's free API** is for non-commercial use.
- **SoccerNet labels** were treated as non-commercial research data (licence not verified).
- **Transfermarkt-derived and FIFA.com-derived tables** have no clear grant for reuse, so they were used
  for local research only.

That is consistent with what this repository is: a paper-only research lab. No order was ever placed, no
product is sold, and every result is a forecast-quality metric, never profit and loss. The only
runtime-approved model, B1, is built from match results alone; no model trained on StatsBomb data was
approved for any runtime path. Nothing here is betting or financial advice.

The consequence for anyone who forks the code: **the MIT licence gives you the code, not the data
rights.** A commercial use of these pipelines needs its own licences, in particular a commercial event-data
agreement in place of StatsBomb Open Data. The lab's own comparison of paid providers is in
[`structured_event_provider_catalog.json`](../data/reference/structured_event_provider_catalog.json)
(public pages, June 2026, nothing purchased).

---

## 5. Getting the data yourself

Nothing needs to be requested from the author. Every source is fetched from upstream with your own
accounts.

| Step | What it gives you | Needs |
|---|---|---|
| `python -m wcdrawlab.cli fetch-public` | The three open CSVs listed in [`data/source_registry.json`](../data/source_registry.json) (martj42 results, Fjelstul matches and tournaments), written to `data/raw/` | No account |
| [`QUICKSTART.md`](../QUICKSTART.md), steps 3 and 4 | The research table and the 2026 forecast targets. The 2026 fixture queue is already tracked; QUICKSTART advises against refreshing it after the tournament | The keys listed in QUICKSTART step 3 (a queue refresh would need `API_FOOTBALL_KEY`) |
| [`ACCOUNT_AND_API_SETUP.md`](ACCOUNT_AND_API_SETUP.md) | Which accounts to create and which environment variables they map to | football-data.org, The Odds API, API-Football |
| StatsBomb Open Data | Clone or download from [the upstream repository](https://github.com/statsbomb/open-data) after reading its user agreement; upstream asks users to register their interest on its website | No key |
| SoccerNet-Echoes | Download from [Hugging Face](https://huggingface.co/datasets/SoccerNet/SN-echoes) into the ignored `data/raw/commentary/` | No NDA; check the dataset page for current access conditions |

After downloading, compare your file hashes with
[`source_provenance.json`](../data/processed/source_provenance.json). Upstream files change over time, so
a different hash usually means a newer upstream version, not a fault.

Be realistic about what a fresh clone can reproduce:

- The test suite and the toolkit run without any data. The integration tests that need ignored datasets
  are skipped with an explicit reason; see
  [`TESTING_AND_DATA_DEPENDENCIES.md`](TESTING_AND_DATA_DEPENDENCIES.md).
- The frozen 2026 prediction ledger and the odds snapshots live in ignored directories, so the
  prospective benchmark cannot be re-scored from a clone. Its tracked record is the manifests and
  decision ledgers in `data/reference/` and the scorecard notes.
- Several research-line runners are single-machine orchestration records with the author's local paths
  in them ([ERRATA E7](ERRATA.md)).
- The paid API-Football corpus cannot be rebuilt without a paid plan.

New sources go through a written request under [`data_requests/pending/`](../data_requests/pending/)
before any code is added; the rules are in [`DATA_SOURCE_GOVERNANCE.md`](DATA_SOURCE_GOVERNANCE.md) and
the per-record provenance rules in [`provenance_policy.md`](../notes/research/provenance_policy.md).

---

## 6. Known inaccuracies in the provenance ledger

[`data/processed/source_provenance.json`](../data/processed/source_provenance.json) is a point-in-time
ledger generated on 2026-06-20 by
[`scripts/build_source_provenance.py`](../scripts/build_source_provenance.py). It has been left as it was
written, in keeping with the lab's habit of not rewriting historical records. The entries below are
wrong or incomplete and should be corrected in the generator, then regenerated. This page is the
corrected reference until then.

| # | Entry | What the ledger says | What is true |
|---|---|---|---|
| 1 | `jfjelstul_worldcup_matches`, `jfjelstul_worldcup_tournaments` | `"license": "MIT"` | Upstream README: **CC-BY-SA 4.0**, attribution and share-alike required. Checked 2026-09-20 |
| 2 | `dato_futbol_fifa_ranking` | `"license": "open (GitHub), Transfermarkt/FIFA-derived"` | That is not a licence. Upstream declares none, and says the table was scraped from FIFA.com; Transfermarkt is not involved. Should read "no licence declared; raw file not redistributed" |
| 3 | `transfermarkt_dcaribou` | `"license": "... (CC-BY-NC-SA per repo)"` | The upstream repository `LICENSE` is CC0 1.0 on the check date. The CC-BY-NC-SA string could not be confirmed. Transfermarkt's own terms are a separate question |
| 4 | `the_odds_api_historical` | `"used_for": "beat-market validation"` | The wording overstates. The early notes it refers to were later reclassified as auxiliary and were not confirmed prospectively ([ERRATA E4](ERRATA.md)). Should read "retrospective market comparison" |
| 5 | `wikipedia_2026_format` | Names Wikipedia as the source of `data/reference/tiebreak_rules_2026.yaml`, with a byte size of 2,930 and a SHA-256 beginning `e73a1780` | The tracked file's own header cites FIFA.com's tie-breaker article plus press corroboration, and it was revised after the ledger was generated: the committed file is 3,960 bytes and its hash no longer matches |
| 6 | Whole file | Nine entries | Sources with no entry: StatsBomb Open Data, API-Football, SoccerNet-Echoes, SoccerNet labels, Open-Meteo |
| 7 | Whole file | Lives at `data/processed/` | It is the one tracked file inside an ignored directory (a deliberate exception noted in `.gitignore`). The path is cited by the governance-protected `configs/approved_models.yaml` and by more than ten research notes, so the file stays where it is |

Related wording elsewhere that should be aligned in the same pass:

- The docstring of `scripts/acquire_statsbomb_open.py` describes the StatsBomb terms as "CC BY-NC-SA
  spirit". StatsBomb Open Data is under its own user agreement, not a Creative Commons licence.
- [`commentary_source_catalog.json`](../data/reference/commentary_source_catalog.json) records StatsBomb
  redistribution as "per agreement". The agreement does not permit redistributing the data.
- Three leftover strings do not match the paper-only posture of the repository: "update before betting"
  in the notes column of `data/seed/worldcup_2026_seed_matches.csv`, a reference to an odds "scan" in the
  notes column of `data/seed/sample_odds_2026.csv`, and "betting-grade system" in the provenance note of
  `data/reference/tiebreak_rules_2026.yaml`.

For model and result corrections, see [`ERRATA.md`](ERRATA.md). For the lab's vocabulary, see
[`GLOSSARY.md`](GLOSSARY.md).
