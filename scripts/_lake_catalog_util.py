"""Catalog/bridge helpers for international-event-lake jobs: OFFICIAL StatsBomb open-data HTTP
(competitions + match lists ONLY), strict team/date normalization, and regulation-result derivation.

External retrieval here is restricted to the OFFICIAL StatsBomb open-data host. Event JSON is NOT
fetched here — that is the lake engine's job (wcdrawlab.research.international_event_lake). This
module only retrieves the small public catalog (competitions.json + matches lists) used to build
the catalog and the strict bridge. research_only.
"""
from __future__ import annotations

import re
import time
import unicodedata
import urllib.error
import urllib.request

OFFICIAL_HOST = "raw.githubusercontent.com"
OFFICIAL_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
USER_AGENT = "wcdrawlab-research/1.0 (StatsBomb open-data, non-commercial research)"
MAX_RETRIES = 2


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _assert_official(url: str) -> None:
    if not url.startswith("https://") or OFFICIAL_HOST not in url or "/statsbomb/open-data/" not in url:
        raise ValueError(f"non-official url refused (official StatsBomb open-data only): {url}")


def get_bytes(url: str, timeout: int = 60) -> bytes:
    """Official-only GET with bounded exponential backoff (<=2 retries)."""
    _assert_official(url)
    last: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310 (https, official public data)
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (404, 410):
                raise
            time.sleep(min(8.0, 0.5 * (2 ** attempt)))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(min(8.0, 0.5 * (2 ** attempt)))
    raise RuntimeError(f"official GET failed after {MAX_RETRIES + 1} attempts: {url}: {last}")


def competitions_url() -> str:
    return f"{OFFICIAL_BASE}/competitions.json"


def matches_url(competition_id: int, season_id: int) -> str:
    return f"{OFFICIAL_BASE}/matches/{int(competition_id)}/{int(season_id)}.json"


# --------------------------------------------------------------------------- normalization
_TEAM_ALIASES = {
    "korea republic": "south korea", "republic of korea": "south korea", "korea dpr": "north korea",
    "ir iran": "iran", "iran islamic republic": "iran", "czechia": "czech republic",
    "usa": "united states", "united states of america": "united states", "u s a": "united states",
    "bosnia and herzegovina": "bosnia", "republic of ireland": "ireland",
    "ivory coast": "cote divoire", "cote d ivoire": "cote divoire",
    "north macedonia": "macedonia", "fyr macedonia": "macedonia",
    "turkiye": "turkey", "china pr": "china", "cape verde islands": "cape verde",
}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_team(name: str | None) -> str:
    if not name:
        return ""
    s = strip_accents(str(name)).lower().strip().replace("&", "and")
    s = re.sub(r"[._'`]", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return _TEAM_ALIASES.get(s, s)


def normalize_date(d: str | None) -> str:
    if not d:
        return ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(d).strip())
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def regulation_result(home_goals, away_goals) -> str:
    try:
        h, a = int(home_goals), int(away_goals)
    except (TypeError, ValueError):
        return ""
    return "home" if h > a else ("away" if h < a else "draw")


def team_set(norm_home: str, norm_away: str) -> frozenset:
    return frozenset((norm_home, norm_away))
