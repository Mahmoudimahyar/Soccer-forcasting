"""Phase 6 - LIVE-READINESS MATRIX for the in-play feature families.

research_only / experimental / not_runtime_approved / not_trade_eligible / not_live_eligible

Classifies ~20 in-play feature families by how close each is to being usable in a LIVE
point-in-time setting, grounded ONLY in local validated artifacts:

  - data/reference/residual_goal_intensity/feature_catalog.csv  (families + source_coverage)
  - data/processed/event_process_snapshots/competition_source_quality.csv (21 capability families)
  - data/reference/dynamic_xg_state_coverage.json / dynamic_xg_state_audit.json (xG leakage rules)
  - data/reference/statsbomb_cache_audit.json / xg_snapshot_join_audit.json (xG source = statsbomb_open)
  - MEMORY apifootball-pro-coverage: API-Football Pro has NO per-event publication time
    (=> historical-only unless a live latency is measured + causal-gated); xG only for newer
    tournaments; shot-location xy unavailable.

CENTRAL TIMESTAMP FACT (drives most classifications)
----------------------------------------------------
Every offline artifact is built from POST-HOC, complete-match event data (StatsBomb open +
API-Football historical). The only time coordinate is the match-clock minute (elapsed), used for
leakage-safe REPLAY. There is NO wall-clock event PUBLICATION timestamp on any source. So a family
can be perfectly point-in-time *replayable offline* yet still be blocked for LIVE use until a
provider's real event-publication latency is measured and causal-gated. We therefore separate:
  - point_in_time_replay_possible  (offline, match-clock gated)  -> almost always TRUE here
  - live_eligible                  (needs measured provider latency + rights + schema parity)

This script does NOT recommend purchasing any provider and makes NO market claims. It only states,
per family, what evidence would be required before a live claim.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LABELS = "research_only/experimental/not_runtime_approved/not_trade_eligible/not_live_eligible"

# Classification vocabulary (per program spec)
C_OFFLINE = "offline_historical_only"
C_RESEARCH = "historical_research_ready"
C_POTENTIAL = "potentially_live_with_verified_provider"
C_LIVE = "live_eligible"
C_LAT = "blocked_by_latency"
C_RIGHTS = "blocked_by_rights"
C_SCHEMA = "blocked_by_schema"
C_NOPIT = "blocked_by_no_point_in_time_history"
C_NOCONTRACT = "blocked_by_missing_provider_contract"


def _f(path: str) -> Path:
    return REPO / path


def load_grounding():
    g = {}
    # feature_catalog families + coverage
    fc = []
    with open(_f("data/reference/residual_goal_intensity/feature_catalog.csv"),
              encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fc.append(r)
    g["feature_catalog"] = fc
    g["families_in_catalog"] = sorted({r["family"] for r in fc})
    # event-process capability families (distinct capability names)
    caps = {}
    cap_path = _f("data/processed/event_process_snapshots/competition_source_quality.csv")
    rows = []
    if cap_path.exists():
        with open(cap_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    # absent/empty in consolidation; fall back to the residual repo's validated artifact
    if not rows:
        alt = Path("C:/Users/Mahyar/worldcup-residual-goal-intensity/"
                   "data/processed/event_process_snapshots/competition_source_quality.csv")
        if alt.exists():
            with open(alt, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
    for r in rows:
        cap = r["capability"]
        caps.setdefault(cap, {"available_verified": 0, "available_partial": 0,
                              "unavailable": 0, "unknown": 0})
        for k in ("available_verified", "available_partial", "unavailable", "unknown"):
            caps[cap][k] += int(r.get(k) or 0)
    g["capabilities"] = caps
    # xg coverage
    try:
        g["xg_cov"] = json.loads(
            _f("data/reference/dynamic_xg_state_coverage.json").read_text(encoding="utf-8"))
    except Exception:
        g["xg_cov"] = {}
    try:
        g["sb_audit"] = json.loads(
            _f("data/reference/statsbomb_cache_audit.json").read_text(encoding="utf-8"))
    except Exception:
        g["sb_audit"] = {}
    return g


# ---- the ~20 feature families with grounded, honest live-readiness reasoning ----
# Each entry ties to a real catalog family/capability and states the timestamp semantics,
# whether offline point-in-time REPLAY is possible, the provider fields/cadence/latency that
# a LIVE version would need, and the evidence required before any live claim.

def build_matrix(g):
    caps = g["capabilities"]

    def cap_status(name):
        c = caps.get(name)
        if not c:
            return "absent"
        tot = sum(c.values())
        if tot and c["available_verified"] == tot:
            return "all_verified"
        if c["available_verified"]:
            return "partial_verified"
        return "weak"

    # xG source facts
    xg_source = g["xg_cov"].get("xg_source", "statsbomb_open")
    rows = []

    def add(family, catalog_link, source, ts_semantics, classification, pit_replay,
            provider_fields, cadence, max_latency, evidence_needed, notes):
        rows.append({
            "feature_family": family,
            "catalog_link": catalog_link,
            "primary_source": source,
            "source_timestamp_semantics": ts_semantics,
            "classification": classification,
            "point_in_time_replay_possible": pit_replay,
            "required_provider_fields": provider_fields,
            "required_cadence": cadence,
            "required_max_latency": max_latency,
            "evidence_needed_before_live": evidence_needed,
            "notes": notes,
        })

    NO_PUB_TS = ("match-clock minute only (elapsed); NO wall-clock event publication timestamp on "
                 "StatsBomb-open / API-Football historical")
    PIT_YES = "yes_offline_matchclock_gated"
    PIT_PARTIAL = "yes_offline_but_feature_lags_real_time"

    # 1 reference match-state (score/time/players) -- the W2 reference inputs
    add("reference_match_state", "feature_catalog:reference_state / cap:match_state",
        "API-Football events (goals/cards/subs) + clock", NO_PUB_TS, C_POTENTIAL, PIT_YES,
        "live score, elapsed minute, red-card count, sub count per team",
        "<=1 update / 30s during match", "<=15s after on-field event",
        "measure API-Football live goal/card publication latency on >=20 live matches; confirm "
        "monotonic clock; verify regulation/ET split live",
        "lowest-barrier family; score+time+players already drive the only validated in-play gains")

    # 2 remaining-time / regulation clock
    add("remaining_regulation_time", "feature_catalog:remaining_regulation_min",
        "match clock", "deterministic from kickoff + elapsed; no external publish lag",
        C_POTENTIAL, PIT_YES, "authoritative elapsed minute + period",
        "continuous", "<=5s clock skew",
        "verify provider clock matches official; handle stoppage-time semantics live",
        "purely derived; only risk is clock source disagreement live")

    # 3 cumulative xG state
    add("cumulative_xg_state", "feature_catalog:recent_chance(cum_xg_*) / cap:shot_xg",
        f"{xg_source} per-shot xG (post-hoc)",
        "post-hoc model output; xG attached AFTER full match processing; no live publish time",
        C_NOCONTRACT, PIT_PARTIAL,
        "per-shot xG with shot match-minute, delivered intra-match",
        "per shot event", "<=30s after shot",
        "a LIVE xG provider contract (StatsBomb/Opta live xG) with measured per-shot delivery "
        "latency; StatsBomb-open is post-hoc & non-commercial -> not live-usable",
        "research result: in-play xG did NOT beat score+Elo; low priority to make live")

    # 4 xG momentum / acceleration (windowed derivatives of xG)
    add("xg_momentum_acceleration", "feature_catalog:xg_momentum/xg_acceleration",
        f"{xg_source} per-shot xG windows",
        "derived from post-hoc xG stream; inherits no-publish-time", C_NOCONTRACT, PIT_PARTIAL,
        "low-latency per-shot xG to compute trailing windows live",
        "per shot event", "<=30s after shot",
        "same live-xG contract as cumulative_xg; plus stability test of windowed derivatives "
        "under live revision (xG values can be revised post-match)",
        "depends entirely on a live xG feed; revisions are a schema/latency risk")

    # 5 shot events (counts/on-target) -- team-level, available on API-Football
    add("shot_events_counts", "feature_catalog:shots_diff/shots_on_target / cap:shot_events",
        "API-Football team-level shots + StatsBomb shot events",
        "post-hoc team stats; API-Football live shot stats lag final reconciliation", C_LAT,
        PIT_YES, "live team shot / shot-on-target counters",
        "<=1 update / 60s", "<=60s",
        "measure API-Football live shot-stat latency & revision rate; team-stat counters are "
        "known to be revised during/after matches",
        "counts (not locations) are obtainable; latency+revision are the open question")

    # 6 shot location (xy)
    add("shot_location_xy", "cap:shot_location / cap:shot_freeze_frame",
        "StatsBomb open (xy + freeze frames)",
        "post-hoc spatial data; no live publication; API-Football has NO xy", C_NOCONTRACT,
        PIT_YES, "live shot x,y coordinates",
        "per shot event", "<=30s after shot",
        "a provider that delivers live shot xy (Opta/StatsBomb live); API-Football verified to "
        "LACK shot locations entirely",
        "hard-blocked for live without a new spatial provider; offline replay fine")

    # 7 big-chance proxy (xG threshold)
    add("big_chance_proxy", "cap:big_chance_proxy",
        f"{xg_source} xG>=0.3 proxy",
        "post-hoc xG threshold; not a provider 'big chance' flag", C_NOCONTRACT, PIT_YES,
        "live xG per shot (to threshold) or provider big-chance flag",
        "per shot event", "<=30s after shot",
        "live xG feed OR a provider-native big-chance event with measured latency",
        "proxy is fine offline; live needs the same xG dependency")

    # 8 possession structure / share
    add("possession_structure", "feature_catalog:possession_territory / cap:possession_structure",
        "StatsBomb event-derived possession; API-Football possession %",
        "post-hoc; live possession % is a smoothed running stat with provider lag", C_LAT,
        PIT_YES, "live possession share / passes",
        "<=1 update / 60s", "<=60s",
        "measure live possession-stat latency & smoothing; confirm definition parity with the "
        "offline event-derived metric",
        "definition mismatch (event-derived vs provider-smoothed) is a schema risk")

    # 9 field tilt / territory
    add("field_tilt_territory", "feature_catalog:field_tilt / cap:field_tilt / cap:territory_thirds",
        "StatsBomb event locations", "post-hoc spatial aggregation; no live publish time",
        C_NOPIT, PIT_YES, "live event locations (passes/touches by third)",
        "per event", "<=60s",
        "a live event-location feed; API-Football lacks granular locations -> needs spatial provider",
        "offline replay solid; live needs granular location stream")

    # 10 box entries
    add("box_entries", "feature_catalog:box_entries / cap:box_entries",
        "StatsBomb event locations",
        "post-hoc location-derived count; no live publish time", C_NOPIT, PIT_YES,
        "live entries-into-box events or locations", "per event", "<=60s",
        "live location/event feed defining box entries; verify definition parity",
        "location-dependent -> same spatial-provider gap as field tilt")

    # 11 deep progression / attack phase
    add("progression_attack_phase",
        "cap:deep_progression / cap:attack_phase / cap:possession_to_shot_chain",
        "StatsBomb event chains",
        "post-hoc possession-chain reconstruction; no live publish time", C_NOPIT, PIT_YES,
        "live ordered event stream sufficient to rebuild possession chains",
        "per event", "<=60s",
        "live full event stream + chain reconstruction validated against offline chains live",
        "most data-hungry families; chain logic is offline-validated only")

    # 12 transition (recoveries/turnovers/counter)
    add("transition_recoveries_turnovers",
        "feature_catalog:transition / cap:recoveries / cap:turnovers / cap:counter_proxy",
        "StatsBomb event-derived recoveries/turnovers",
        "post-hoc; no live publish time", C_NOPIT, PIT_YES,
        "live possession-change events", "per event", "<=60s",
        "live event stream with possession ownership; confirm recovery/turnover definitions",
        "definition-heavy; offline-only until live event stream verified")

    # 13 pressure / counterpress proxy
    add("pressure_counterpress_proxy", "cap:pressure / cap:counterpress_proxy",
        "StatsBomb pressure events (proxy)",
        "post-hoc; pressure is a StatsBomb-specific event type, not in API-Football", C_NOCONTRACT,
        PIT_YES, "live pressure events (StatsBomb-style) or accepted proxy",
        "per event", "<=60s",
        "a provider that emits pressure-type events live; API-Football does not have them",
        "provider-specific event type -> contract-blocked for live")

    # 14 set pieces (corners/free kicks)
    add("set_pieces", "feature_catalog:set_pieces(corners/att_free_kicks)",
        "API-Football + StatsBomb set-piece events",
        "post-hoc counts; corners/FK are discrete, low-latency in most live feeds", C_LAT,
        PIT_YES, "live corner / free-kick counters",
        "<=1 update / 60s", "<=60s",
        "measure live set-piece event latency; these are usually reliable live signals",
        "relatively live-friendly (discrete events); latency just needs measuring")

    # 15 cards / sendings-off
    add("cards_sendings_off",
        "feature_catalog:quality_availability(yellow/sendoff) / cap:cards",
        "API-Football card events (verified available)",
        "discrete events with on-field minute; API-Football delivers live but lag unmeasured",
        C_POTENTIAL, PIT_YES, "live yellow/red events with minute + player id",
        "per event", "<=15s after on-field event",
        "measure live card publication latency; reconcile 2nd-yellow vs straight-red live",
        "high-value low-volume signal; API-Football coverage already verified historically")

    # 16 substitutions
    add("substitutions",
        "feature_catalog:quality_availability(subs_used) / events:subs",
        "API-Football substitution events (verified available)",
        "discrete events; live publish lag unmeasured", C_POTENTIAL, PIT_YES,
        "live substitution events with minute + in/out player ids",
        "per event", "<=30s after on-field event",
        "measure live sub publication latency; subs sometimes published late vs broadcast",
        "available historically; subs feed quality is the live unknown")

    # 17 lineups / formation (pre-match state)
    add("lineups_formation",
        "MEMORY apifootball-pro: lineups+benches+player ids+positions+formation verified",
        "API-Football lineups (verified, 100% on pilot)",
        "published ~T-60min pre-kickoff; effectively point-in-time for pre-match",
        C_POTENTIAL, PIT_YES, "confirmed XI + formation at publication time",
        "once pre-match (+ in-play changes)", "<=publish at T-60; <=60s for in-play role changes",
        "verify live lineup publish time vs kickoff; player plane was an honest NEGATIVE so low ROI",
        "best-covered family; but research showed no pre-match 1X2 gain over Elo")

    # 18 player availability / key-player (derived from lineups)
    add("player_availability_keyplayer",
        "MEMORY player_plane: key-availability feature (neutral vs Elo)",
        "API-Football lineups + player history",
        "derived from lineups (pre-match point-in-time)", C_POTENTIAL, PIT_YES,
        "confirmed XI + a player-importance prior computed from strictly-prior matches",
        "once pre-match", "<=publish at T-60",
        "leakage-safe player-importance prior; research showed neutral/negative vs Elo",
        "feasible live but unproven value; deprioritized by prior nulls")

    # 19 weather / venue / travel-rest (contextual, pre-match)
    add("weather_venue_travel_rest",
        "schemas (venue/weather/travel-rest) from Part-C scaffolding",
        "venues_2026.csv + external weather (not in local validated set)",
        "venue static; weather forecast point-in-time; travel/rest deterministic from schedule",
        C_NOPIT, PIT_YES, "as-of weather forecast + confirmed venue + fixture schedule",
        "hourly (weather)", "forecast as-of kickoff",
        "a point-in-time weather history/forecast source with as-of timestamps; only venue+schedule "
        "are locally validated (weather history is NOT in the local validated artifacts)",
        "venue/travel deterministic; weather needs an as-of-timestamped source not yet on disk")

    # 20 market / odds in-play
    add("market_inplay_odds",
        "source_provenance: the_odds_api (pre-match only on hand)",
        "The Odds API (pre-match snapshots locally)",
        "pre-match snapshot_time<=kickoff; in-play odds NOT in local validated artifacts",
        C_NOPIT, "no_local_inplay_history",
        "in-play odds stream with snapshot timestamps", "<=1 update / 10s",
        "<=10s", "an in-play odds feed with per-snapshot timestamps; only pre-match odds exist "
        "locally, so in-play market features have NO point-in-time history to backtest",
        "market is research-relevant but there is zero local in-play-odds history to validate")

    # 21 prior-quality / strength priors (cross-match, kickoff-ordered)
    add("prior_strength_quality_priors",
        "feature_catalog:prior_xg_quality / dynamic priors (kickoff-ordered)",
        "StatsBomb/API-Football historical aggregated to strictly-prior matches",
        "as-of kickoff date (strictly earlier matches only); inherently point-in-time", C_RESEARCH,
        PIT_YES, "rolling prior built from completed prior matches only",
        "updated per completed match", "n/a (pre-match, no intra-match latency)",
        "none beyond keeping the strictly-prior ordering; already leakage-safe and replayable",
        "the most live-ready conceptually (pre-match, as-of), but depends on the upstream "
        "event feeds it aggregates")

    return rows


def main():
    g = load_grounding()
    rows = build_matrix(g)

    # JSON
    out_json = {
        "title": "Live-readiness matrix for in-play feature families",
        "central_timestamp_fact": (
            "All local artifacts are post-hoc, complete-match; the only time coordinate is the "
            "match-clock minute (enables offline point-in-time REPLAY). No source carries a "
            "wall-clock event PUBLICATION timestamp, so offline-replayable != live-eligible."),
        "no_2026_wc_data_used": True,
        "no_provider_purchase_recommendations": True,
        "no_market_claims": True,
        "classification_vocabulary": [
            C_OFFLINE, C_RESEARCH, C_POTENTIAL, C_LIVE, C_LAT, C_RIGHTS, C_SCHEMA, C_NOPIT,
            C_NOCONTRACT],
        "grounding_artifacts": [
            "data/reference/residual_goal_intensity/feature_catalog.csv",
            "data/processed/event_process_snapshots/competition_source_quality.csv",
            "data/reference/dynamic_xg_state_coverage.json",
            "data/reference/statsbomb_cache_audit.json",
            "MEMORY:apifootball-pro-coverage"],
        "families": rows,
        "classification_counts": {},
        "n_families": len(rows),
        "labels": LABELS,
    }
    counts = {}
    for r in rows:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1
    out_json["classification_counts"] = counts

    (REPO / "data/reference/live_readiness_matrix.json").write_text(
        json.dumps(out_json, indent=2), encoding="utf-8")

    # CSV
    cols = ["feature_family", "catalog_link", "primary_source", "source_timestamp_semantics",
            "classification", "point_in_time_replay_possible", "required_provider_fields",
            "required_cadence", "required_max_latency", "evidence_needed_before_live", "notes"]
    csv_path = REPO / "data/reference/live_readiness_matrix.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(json.dumps({"status": "complete", "n_families": len(rows),
                      "classification_counts": counts,
                      "csv": str(csv_path).replace("\\", "/"),
                      "json": str(REPO / "data/reference/live_readiness_matrix.json")
                      .replace("\\", "/")}, indent=2))


if __name__ == "__main__":
    main()
