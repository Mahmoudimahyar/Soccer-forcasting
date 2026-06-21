"""Safe, read-only provider health checks.

Hard secret-safety rules enforced here:
  - The configured key is read with os.getenv ONLY to send it in a request header/param. It is
    NEVER returned, printed, logged, hashed, or placed in any error message.
  - On failure we capture the EXCEPTION TYPE NAME only (never str(e)) — important because The Odds
    API carries the key in the URL query string, and exception messages / resp.url would echo it.
  - We never store response bodies or response URLs. Only the HTTP status CLASS (e.g. "4xx") and a
    small set of non-secret signals (e.g. provider error flag, rate-limit header values) are kept.

Nothing here counts against paid quotas beyond a single minimal read-only endpoint per provider
(API-Football /status, Odds API /sports, football-data /competitions are free or negligible).
"""
from __future__ import annotations

import os
from typing import Any

try:
    import requests
except Exception:  # pragma: no cover - requests is a project dep
    requests = None  # type: ignore

_TIMEOUT = 15.0


def _status_class(code: int) -> str:
    return f"{code // 100}xx"


def _configured(env_name: str) -> str:
    return "SET" if os.getenv(env_name) else "MISSING"


def _base(provider: str, endpoint: str, env_name: str | None) -> dict[str, Any]:
    return {
        "provider": provider,
        "endpoint": endpoint,
        "configured": _configured(env_name) if env_name else "n/a (keyless)",
        "auth_accepted": "not_tested",
        "mode_detected": "unknown",
        "status_class": "not_tested",
        "provider_error_flag": None,
        "rate_limit": "unknown",
        "error_class": None,
    }


def _safe_get(url: str, *, headers: dict | None = None, params: dict | None = None):
    """Return (status_code, headers, json_or_none) or raise. Never leak inputs on error."""
    if requests is None:
        raise RuntimeError("requests_unavailable")
    resp = requests.get(url, headers=headers or {}, params=params or {}, timeout=_TIMEOUT)
    body = None
    try:
        body = resp.json()
    except Exception:
        body = None
    return resp.status_code, dict(resp.headers), body


def check_open_meteo() -> dict[str, Any]:
    r = _base("open_meteo", "GET /v1/forecast", None)
    try:
        code, _h, _b = _safe_get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": 40.0, "longitude": -75.0, "hourly": "temperature_2m", "forecast_days": 1},
        )
        r["status_class"] = _status_class(code)
        r["auth_accepted"] = "yes (keyless)" if code < 400 else "no"
        r["mode_detected"] = "direct API"
    except Exception as e:  # noqa: BLE001
        r["status_class"] = "network_error"
        r["error_class"] = type(e).__name__
    return r


def check_odds_api() -> dict[str, Any]:
    r = _base("the_odds_api", "GET /v4/sports", "ODDS_API_KEY")
    key = os.getenv("ODDS_API_KEY")
    if not key:
        return r
    try:
        # /sports does NOT count against quota; key is a query param -> never log url/exception msg
        code, headers, _b = _safe_get("https://api.the-odds-api.com/v4/sports", params={"apiKey": key})
        r["status_class"] = _status_class(code)
        r["auth_accepted"] = "yes" if code < 400 else "no"
        r["mode_detected"] = "direct API"
        rem = headers.get("x-requests-remaining")
        used = headers.get("x-requests-used")
        if rem is not None:
            r["rate_limit"] = f"remaining={rem} used={used}"  # header values are not secrets
    except Exception as e:  # noqa: BLE001 - never include str(e): url carries the key
        r["status_class"] = "network_error"
        r["error_class"] = type(e).__name__
    return r


def check_football_data() -> dict[str, Any]:
    r = _base("football_data_org", "GET /v4/competitions/WC", "FOOTBALL_DATA_KEY")
    key = os.getenv("FOOTBALL_DATA_KEY")
    if not key:
        return r
    try:
        code, headers, _b = _safe_get(
            "https://api.football-data.org/v4/competitions/WC", headers={"X-Auth-Token": key}
        )
        r["status_class"] = _status_class(code)
        r["auth_accepted"] = "yes" if code < 400 else "no"
        r["mode_detected"] = "direct API"
        rem = headers.get("X-Requests-Available-Minute") or headers.get("X-RequestCounter-Reset")
        if rem is not None:
            r["rate_limit"] = f"per-minute-available~{rem}"
    except Exception as e:  # noqa: BLE001
        r["status_class"] = "network_error"
        r["error_class"] = type(e).__name__
    return r


def _check_api_football(mode: str) -> dict[str, Any]:
    """Test ONE auth mode for the API-Football key without leaking it.
    mode='direct' -> api-sports.io host + x-apisports-key
    mode='rapidapi' -> RapidAPI host + x-rapidapi-key/host
    """
    key = os.getenv("API_FOOTBALL_KEY")
    if mode == "direct":
        url = "https://v3.football.api-sports.io/status"
        headers = {"x-apisports-key": key or ""}
        label = "direct (api-sports.io / x-apisports-key)"
    else:
        url = "https://api-football-v1.p.rapidapi.com/v3/status"
        headers = {"x-rapidapi-key": key or "", "x-rapidapi-host": "api-football-v1.p.rapidapi.com"}
        label = "rapidapi (api-football-v1.p.rapidapi.com / x-rapidapi-key)"
    r = _base("api_football", f"GET /status [{label}]", "API_FOOTBALL_KEY")
    r["mode_detected"] = mode
    if not key:
        return r
    try:
        code, _h, body = _safe_get(url, headers=headers)
        r["status_class"] = _status_class(code)
        # API-Football returns HTTP 200 even on auth failure, with an "errors" object naming a
        # token error. Treat presence of errors as auth NOT accepted. Store only the boolean.
        has_errors = bool(isinstance(body, dict) and body.get("errors"))
        r["provider_error_flag"] = has_errors
        r["auth_accepted"] = "yes" if (code < 400 and not has_errors) else "no"
    except Exception as e:  # noqa: BLE001
        r["status_class"] = "network_error"
        r["error_class"] = type(e).__name__
    return r


def check_api_football_direct() -> dict[str, Any]:
    return _check_api_football("direct")


def check_api_football_rapidapi() -> dict[str, Any]:
    return _check_api_football("rapidapi")


def run_all() -> list[dict[str, Any]]:
    return [
        check_open_meteo(),
        check_odds_api(),
        check_football_data(),
        check_api_football_direct(),
        check_api_football_rapidapi(),
    ]
