"""Phase 4: research-only commentary-to-event alignment engine (deterministic; no LLM/proprietary NLP).

Levels:
  L0 time-only      : a GT event is 'witnessed' if any commentary segment falls within the time window.
  L1 keyword/rule   : witnessed only if a within-window segment's text CLAIMS that canonical event type.
  L2 entity-aware   : (optional) restrict to segments mentioning the event team name.
  L3 latency offset : median (t_seg - t_event) estimated on TRAIN matches only; applied to test timing.

Metrics (per canonical type):
  recall_L0  = GT events with any within-window segment / GT events
  recall_L1  = GT events with a within-window keyword-claiming segment / GT events
  precision_L1 = within-window-correct claims / all claims of that type   (commentary-claim correctness)
  timing dt  = t_seg - t_event for L1 matched pairs (uncalibrated); calibrated dt = dt - train_offset

research_only / historical_weak_supervision_only / not_live_eligible.
"""
from __future__ import annotations

import re
import statistics
from collections import defaultdict

# Preregistered English keyword rules (transparent, no LLM). Word-boundary regex on normalized text.
KEYWORD_RULES = {
    "goal": [r"\bgoal\b", r"\bscores?\b", r"\bscored\b", r"\bnets?\b", r"into the net", r"finds the net",
             r"makes it \d", r"the back of the net"],
    "yellow_card": [r"yellow card", r"\bbooked\b", r"\bbooking\b", r"\bcaution(ed)?\b", r"shown a yellow"],
    "red_card": [r"red card", r"sent off", r"dismissed", r"marching orders", r"shown a red"],
    "second_yellow": [r"second yellow", r"two yellow", r"another yellow"],
    "substitution": [r"substitution", r"comes on", r"comes off", r"replaced", r"is replaced",
                     r"makes a (change|substitution)", r"off he comes", r"on he comes"],
    "corner": [r"\bcorner\b", r"corner kick", r"from the corner"],
    "penalty_awarded": [r"\bpenalty\b", r"spot kick", r"penalty kick", r"from the spot"],
    "offside": [r"\boffside\b", r"flag is up", r"flag goes up"],
    "foul": [r"\bfoul\b", r"free kick", r"brings .* down", r"\bfree-kick\b"],
    "shot_on_target": [r"\bshot\b", r"\beffort\b", r"\bstrikes?\b", r"\bsaved?\b", r"\bsave\b", r"on target"],
    "shot": [r"\bshot\b", r"\beffort\b", r"off target", r"wide of", r"over the bar"],
    "kickoff": [r"kick[- ]?off", r"get(s)? us under way", r"under way", r"we are under way"],
}
SUPPORTED_TYPES = list(KEYWORD_RULES.keys())
_COMPILED = {k: [re.compile(p) for p in v] for k, v in KEYWORD_RULES.items()}


def text_claims_event(norm_text: str, canonical: str) -> bool:
    pats = _COMPILED.get(canonical)
    if not pats:
        return False
    return any(p.search(norm_text or "") for p in pats)


def _by_half(items):
    d = defaultdict(list)
    for it in items:
        d[it["half"]].append(it)
    return d


def estimate_train_offset(events_by_match, segments_by_match, train_ids, window_s=45.0):
    """Median (t_seg - t_event) over TRAIN keyword-matched pairs. NEVER uses test matches."""
    dts = []
    for mid in train_ids:
        evs, segs = events_by_match.get(mid, []), segments_by_match.get(mid, [])
        seg_h = _by_half(segs)
        for e in evs:
            ct = e["canonical"]
            if ct not in KEYWORD_RULES:
                continue
            cands = [s for s in seg_h.get(e["half"], [])
                     if abs(s["t_s"] - e["t_s"]) <= window_s and text_claims_event(s["norm"], ct)]
            if cands:
                nearest = min(cands, key=lambda s: abs(s["t_s"] - e["t_s"]))
                dts.append(nearest["t_s"] - e["t_s"])
    return statistics.median(dts) if dts else 0.0


def evaluate(events_by_match, segments_by_match, test_ids, window_s=45.0, offset_s=0.0):
    """Per-type metrics on the test matches. offset_s applied to event time (calibrated alignment)."""
    per = {t: {"n_events": 0, "n_claims": 0, "recall_L0_hits": 0, "recall_L1_hits": 0,
               "precision_hits": 0, "dt": []} for t in SUPPORTED_TYPES}
    for mid in test_ids:
        evs, segs = events_by_match.get(mid, []), segments_by_match.get(mid, [])
        seg_h = _by_half(segs)
        # recall side: per GT event
        for e in evs:
            ct = e["canonical"]
            if ct not in per:
                continue
            per[ct]["n_events"] += 1
            et = e["t_s"] + offset_s
            in_win = [s for s in seg_h.get(e["half"], []) if abs(s["t_s"] - et) <= window_s]
            if in_win:
                per[ct]["recall_L0_hits"] += 1
            kw = [s for s in in_win if text_claims_event(s["norm"], ct)]
            if kw:
                per[ct]["recall_L1_hits"] += 1
                nearest = min(kw, key=lambda s: abs(s["t_s"] - et))
                per[ct]["dt"].append(nearest["t_s"] - et)
        # precision side: per claiming commentary segment
        ev_h = _by_half(evs)
        for s in segs:
            for ct in SUPPORTED_TYPES:
                if text_claims_event(s["norm"], ct):
                    per[ct]["n_claims"] += 1
                    near_ev = [e for e in ev_h.get(s["half"], [])
                               if e["canonical"] == ct and abs((e["t_s"] + offset_s) - s["t_s"]) <= window_s]
                    if near_ev:
                        per[ct]["precision_hits"] += 1
    # finalize
    rows = {}
    for t, d in per.items():
        ne, nc = d["n_events"], d["n_claims"]
        recall_L0 = d["recall_L0_hits"] / ne if ne else None
        recall_L1 = d["recall_L1_hits"] / ne if ne else None
        precision = d["precision_hits"] / nc if nc else None
        f1 = (2 * precision * recall_L1 / (precision + recall_L1)
              if (precision and recall_L1 and (precision + recall_L1) > 0) else None)
        dts = [abs(x) for x in d["dt"]]
        rows[t] = {"n_events": ne, "n_claims": nc, "recall_L0": recall_L0, "recall_L1": recall_L1,
                   "precision_L1": precision, "f1_L1": f1, "n_pairs": len(d["dt"]),
                   "timing_median_abs": statistics.median(dts) if dts else None,
                   "timing_mae": (sum(dts) / len(dts)) if dts else None,
                   "dt_signed_median": statistics.median(d["dt"]) if d["dt"] else None}
    return rows
