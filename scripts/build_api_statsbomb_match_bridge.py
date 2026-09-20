"""Phase 3 (xG bridge): build the EXACT API-Football <-> StatsBomb open-data match bridge.

For each senior MEN'S INTERNATIONAL competition present in BOTH sources (FIFA World Cup 2018 & 2022,
UEFA Euro 2020 & 2024, Copa America 2024), accept a 1:1 link ONLY when ALL exact criteria agree:
  1. exact competition + season (fixed mapping below),
  2. exact normalized home/away team agreement (orientation-aware; swapped orientation only with swapped score),
  3. exact kickoff-DATE agreement (UTC calendar date == StatsBomb match_date),
  4. exact final-SCORE agreement (StatsBomb 90+ET score == API-Football fulltime + extratime increment,
     shootout excluded on both sides),
  5. unambiguous (exactly ONE StatsBomb candidate on the same date+team-pair within the comp-season).

ANY ambiguity, date mismatch, or score mismatch REJECTS the pair (recorded with a reason). No fuzzy /
probabilistic name linking is used to force a match. Deterministic + resumable (pure function of inputs).

Outputs (derived only; raw external data stays gitignored, never committed):
  data/processed/api_statsbomb_match_bridge_v1.csv         (accepted exact rows)
  data/processed/api_statsbomb_match_bridge_v1.audit.json  (counts, rejections, source hashes)

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research_jobs"))

import _common as C  # noqa: E402  (load_corpus + INTL_LEAGUES)
from wcdrawlab.research.paid_source import result_semantics as RS  # noqa: E402

BRIDGE_BUILDER_VERSION = "api_statsbomb_bridge_v1"
RAW_SB = ROOT / "data/raw/statsbomb_open"

# Fixed competition mapping: (api_league_id, api_season) <-> (sb_competition_id, sb_season_id) + label.
COMP_MAP = [
    {"label": "FIFA World Cup 2018", "api": (1, 2018), "sb": (43, 3)},
    {"label": "FIFA World Cup 2022", "api": (1, 2022), "sb": (43, 106)},
    {"label": "UEFA Euro 2020", "api": (4, 2020), "sb": (55, 43)},
    {"label": "UEFA Euro 2024", "api": (4, 2024), "sb": (55, 282)},
    {"label": "Copa America 2024", "api": (9, 2024), "sb": (223, 282)},
]

# Shared canonical team-name folding. Both source vocabularies fold to ONE token. This is exact-token
# normalization (alias table), NOT fuzzy matching: a name not in the table falls through unchanged and
# must still agree exactly across sources.
_CANON = {
    # API-Football variants
    "USA": "United States", "Czechia": "Czech Republic", "FYR Macedonia": "North Macedonia",
    "Korea Republic": "South Korea", "Rep. Of Ireland": "Republic of Ireland",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina", "IR Iran": "Iran",
    "Turkiye": "Turkey", "T�rkiye": "Turkey", "Türkiye": "Turkey",
    # StatsBomb variants (mostly already aligned; listed for explicitness)
    "United States": "United States", "Czech Republic": "Czech Republic",
    "North Macedonia": "North Macedonia", "South Korea": "South Korea",
}


def canon(name: str) -> str:
    if name is None:
        return ""
    t = str(name).strip()
    # repair the common mojibake for Turkiye/Turkey, then alias-fold
    if t in _CANON:
        return _CANON[t]
    if "rkiye" in t or "rkey" in t.lower():
        return "Turkey"
    return t


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_obj(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def api_final_after_et(score: dict):
    """API-Football final (90+ET, shootout EXCLUDED) cumulative goals.

    score.fulltime = regulation; score.extratime = goals scored DURING ET (increment). The StatsBomb-
    comparable final = fulltime + extratime_increment. Returns (home, away) or None if regulation missing.
    """
    score = score or {}
    ft = score.get("fulltime") or {}
    et = score.get("extratime") or {}
    fh, fa = ft.get("home"), ft.get("away")
    if fh is None or fa is None:
        return None
    eh, ea = et.get("home") or 0, et.get("away") or 0
    return fh + eh, fa + ea


def load_api_fixtures():
    """Return {(api_league_id, api_season): [fixture,...]} restricted to the target comps, with events."""
    fx, ev, _ln = C.load_corpus()
    out = {m["api"]: [] for m in COMP_MAP}
    by_id = {}
    for fid, f in fx.items():
        lg = f.get("league", {})
        key = (lg.get("id"), lg.get("season"))
        if key in out:
            out[key].append((fid, f))
            by_id[fid] = f
    return out, ev


def load_sb_matches(sb_key):
    cid, sid = sb_key
    fp = RAW_SB / "matches" / str(cid) / f"{sid}.json"
    if not fp.exists():
        return [], None
    raw = fp.read_bytes()
    return json.loads(raw.decode("utf-8")), _sha256_bytes(raw)


def sb_row_view(mm):
    """Normalized view of a StatsBomb match row."""
    return {
        "sb_match_id": int(mm["match_id"]),
        "date": mm.get("match_date"),
        "home": mm["home_team"]["home_team_name"],
        "away": mm["away_team"]["away_team_name"],
        "home_score": mm.get("home_score"),
        "away_score": mm.get("away_score"),
        "norm_home": canon(mm["home_team"]["home_team_name"]),
        "norm_away": canon(mm["away_team"]["away_team_name"]),
    }


def match_one_fixture(fx_id, fx, ev_map, sb_rows, label, api_key, sb_key, sb_sha):
    """Return (accepted_row | None, rejection | None). Pure function of inputs."""
    teams = fx.get("teams", {})
    api_home = teams.get("home", {}).get("name")
    api_away = teams.get("away", {}).get("name")
    nh, na = canon(api_home), canon(api_away)
    date = (fx.get("fixture", {}).get("date") or "")[:10]
    score = fx.get("score") or {}
    final = api_final_after_et(score)
    can = RS.canonical_result(fx, ev_map.get(fx_id, []))
    reg_h, reg_a = can["official_regulation_home_goals"], can["official_regulation_away_goals"]

    base = {
        "api_fixture_id": int(fx_id), "competition_label": label,
        "api_home": api_home, "api_away": api_away, "norm_home": nh, "norm_away": na,
        "kickoff_date": date,
    }
    if not nh or not na:
        return None, {**base, "reason": "team_unresolved"}
    if final is None:
        return None, {**base, "reason": "api_final_score_missing"}

    # candidate StatsBomb rows in the SAME comp-season on the SAME calendar date with the SAME team pair
    # (orientation-aware). Collect both same and swapped orientation.
    cand = []
    for r in sb_rows:
        if r["date"] != date:
            continue
        same = (r["norm_home"] == nh and r["norm_away"] == na)
        swap = (r["norm_home"] == na and r["norm_away"] == nh)
        if same:
            cand.append((r, "same"))
        elif swap:
            cand.append((r, "swapped"))

    if not cand:
        # distinguish date_mismatch (team pair exists in comp-season but on a different date) vs none
        team_pair_elsewhere = any(
            (r["norm_home"] == nh and r["norm_away"] == na) or (r["norm_home"] == na and r["norm_away"] == nh)
            for r in sb_rows
        )
        return None, {**base, "reason": "date_mismatch" if team_pair_elsewhere else "no_statsbomb_candidate"}

    if len(cand) > 1:
        return None, {**base, "reason": "ambiguous_multiple_candidates",
                      "n_candidates": len(cand),
                      "candidate_sb_ids": [c[0]["sb_match_id"] for c in cand]}

    r, orientation = cand[0]
    # score agreement (orientation-aware): StatsBomb final (90+ET, no shootout) == API final after-ET
    fh, fa = final
    sh, sa = r["home_score"], r["away_score"]
    if orientation == "same":
        score_ok = (sh == fh and sa == fa)
        out_home, out_away = fh, fa
    else:  # swapped: SB home==API away
        score_ok = (sh == fa and sa == fh)
        out_home, out_away = fh, fa  # always reported in API orientation

    if not score_ok:
        return None, {**base, "reason": "score_mismatch", "sb_match_id": r["sb_match_id"],
                      "orientation": orientation, "api_final": [fh, fa], "sb_final": [sh, sa]}

    api_src_sha = _sha256_obj(ev_map.get(fx_id, []))
    bridge_id = hashlib.sha256(f"{fx_id}|{r['sb_match_id']}".encode("utf-8")).hexdigest()[:16]
    row = {
        "bridge_id": bridge_id,
        "api_fixture_id": int(fx_id), "sb_match_id": r["sb_match_id"],
        "competition_label": label,
        "api_league_id": api_key[0], "api_season": api_key[1],
        "sb_competition_id": sb_key[0], "sb_season_id": sb_key[1],
        "comp_type": "international",
        "kickoff_date": date,
        "api_home": api_home, "api_away": api_away, "sb_home": r["home"], "sb_away": r["away"],
        "norm_home": nh, "norm_away": na, "orientation": orientation,
        "final_home_goals": out_home, "final_away_goals": out_away,
        "api_regulation_home": reg_h, "api_regulation_away": reg_a,
        "api_result_type": can["final_result_type"],
        "api_source_sha256": api_src_sha, "sb_match_sha256": sb_sha,
        "bridge_confidence": "exact", "bridge_builder_version": BRIDGE_BUILDER_VERSION,
    }
    return row, None


def build():
    api_by_comp, ev_map = load_api_fixtures()
    accepted, rejected = [], []
    per_comp = {}
    for m in COMP_MAP:
        label, api_key, sb_key = m["label"], m["api"], m["sb"]
        fixtures = api_by_comp.get(api_key, [])
        sb_matches, sb_sha = load_sb_matches(sb_key)
        sb_rows = [sb_row_view(mm) for mm in sb_matches]
        acc = rej = 0
        for fx_id, fx in fixtures:
            row, rejection = match_one_fixture(fx_id, fx, ev_map, sb_rows, label, api_key, sb_key, sb_sha)
            if row is not None:
                accepted.append(row); acc += 1
            else:
                rejected.append(rejection); rej += 1
        per_comp[label] = {
            "api_fixtures": len(fixtures), "sb_matches": len(sb_rows),
            "accepted": acc, "rejected": rej,
        }
    return accepted, rejected, per_comp


def main():
    accepted, rejected, per_comp = build()
    out_dir = ROOT / "data/processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_fp = out_dir / "api_statsbomb_match_bridge_v1.csv"
    audit_fp = out_dir / "api_statsbomb_match_bridge_v1.audit.json"

    # write CSV (deterministic column order; sorted by competition then date then api_fixture_id)
    cols = ["bridge_id", "api_fixture_id", "sb_match_id", "competition_label", "api_league_id", "api_season",
            "sb_competition_id", "sb_season_id", "comp_type", "kickoff_date", "api_home", "api_away",
            "sb_home", "sb_away", "norm_home", "norm_away", "orientation", "final_home_goals",
            "final_away_goals", "api_regulation_home", "api_regulation_away", "api_result_type",
            "api_source_sha256", "sb_match_sha256", "bridge_confidence", "bridge_builder_version"]
    accepted_sorted = sorted(accepted, key=lambda r: (r["competition_label"], r["kickoff_date"], r["api_fixture_id"]))
    import csv
    with csv_fp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in accepted_sorted:
            w.writerow(r)

    from collections import Counter
    rej_by_reason = Counter(r["reason"] for r in rejected)
    audit = {
        "bridge_builder_version": BRIDGE_BUILDER_VERSION,
        "total_accepted": len(accepted),
        "total_rejected": len(rejected),
        "rejections_by_reason": dict(rej_by_reason),
        "per_competition": per_comp,
        "accepted_bridge_id_digest": _sha256_obj(sorted(r["bridge_id"] for r in accepted)),
        "rejected_examples": rejected[:40],
        "note": "raw StatsBomb + API-Football data is gitignored; only derived hashes/counts/metrics tracked.",
    }
    audit_fp.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"accepted (exact) : {len(accepted)}")
    print(f"rejected         : {len(rejected)}  {dict(rej_by_reason)}")
    for label, st in per_comp.items():
        print(f"  {label}: api={st['api_fixtures']} sb={st['sb_matches']} "
              f"accepted={st['accepted']} rejected={st['rejected']}")
    print(f"wrote {csv_fp}")
    print(f"wrote {audit_fp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
