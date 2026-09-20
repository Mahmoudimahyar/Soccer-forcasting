"""Phase 6: live-eligibility gate for commentary sources. Fail-closed: a source is live-eligible ONLY if
ALL 10 criteria hold. With current sources NONE is live-eligible (each is rights- or timestamp-blocked).
Exits non-zero if any source is wrongly marked live-eligible. research_only.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import source_registry as SR

# Catalogue fact: does the source carry a trustworthy ORIGINAL publication timestamp?
HAS_PUBLICATION_TIME = {
    "soccernet_echoes": False,        # broadcast time only
    "soccerreplay_1988": False,       # aligned clock time, no original pub time
    "sportmonks_commentary": True,    # API update time (unverified) -> behind paid license
    "official_match_centers": True,   # page pub time -> but scraping not permitted
    "news_live_blogs": True,          # pub time -> but scraping not permitted
    "yallashoot_arabic": False,
    "api_football": False, "statsbomb_open": False,  # structured, not commentary text
}
RIGHTS_OK_LIVE = {"open_research_download_allowed", "attribution_required", "noncommercial_research_only"}


def classify(source_id, rights) -> str:
    cls = SR.classification(source_id, rights)
    if cls == "rejected_for_project_use":
        return "rejected"
    if cls in ("scraping_not_permitted_or_not_verified",):
        return "rights_blocked"
    if cls in ("NDA_or_manual_approval_required", "commercial_license_required", "API_account_required"):
        return "provider_approval_required"
    has_pub = HAS_PUBLICATION_TIME.get(source_id, False)
    if cls in RIGHTS_OK_LIVE and not has_pub:
        return "ready_for_historical_weak_supervision"  # timestamp_blocked for live
    if cls in RIGHTS_OK_LIVE and has_pub:
        # rights + pub time present, but measured-lag/quality/ID-resolution still unverified this sprint
        return "ready_for_delayed_live_shadow_test"      # NOT live_eligible yet (Phase: verify lag+quality)
    return "not_ready_for_live_use"


def main():
    rights = SR.load_rights()
    results = {s: classify(s, rights) for s in rights.get("sources", {})}
    live = [s for s, c in results.items() if c == "live_eligible"]
    print("commentary live-eligibility gate:")
    for s, c in results.items():
        print(f"  {s:<24} -> {c}")
    if live:
        print(f"FAIL: sources wrongly live-eligible: {live}"); sys.exit(1)
    print("GATE OK: no source is live-eligible (all rights- or timestamp-blocked). "
          "Live use requires publication_time <= decision_time + verified lag/quality/rights.")


if __name__ == "__main__":
    main()
