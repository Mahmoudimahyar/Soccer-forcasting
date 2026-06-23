"""Phase 6 live-eligibility + isolation tests. Synthetic; no network."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from wcdrawlab.research.commentary import availability, source_registry as SR  # noqa: E402
import validate_commentary_live_eligibility as GATE  # noqa: E402


def test_unknown_publication_time_never_live_eligible():
    # open rights but no pub time -> historical weak supervision, never live
    assert GATE.classify("soccernet_echoes", SR.load_rights()) == "ready_for_historical_weak_supervision"


def test_rights_uncertainty_blocks_live():
    r = SR.load_rights()
    assert GATE.classify("news_live_blogs", r) == "rights_blocked"
    assert GATE.classify("soccerreplay_1988", r) == "provider_approval_required"
    assert GATE.classify("sportmonks_commentary", r) == "provider_approval_required"


def test_no_source_is_live_eligible_now():
    r = SR.load_rights()
    assert not any(GATE.classify(s, r) == "live_eligible" for s in r.get("sources", {}))


def test_line_published_after_decision_is_blocked():
    assert availability.live_publication_safe("2026-06-24T16:31:00+00:00", "2026-06-24T16:30:00+00:00") is False


def test_safety_lag_enforced():
    assert availability.live_publication_safe("2026-06-24T16:29:50+00:00", "2026-06-24T16:30:00+00:00",
                                              safety_lag_seconds=30) is False


def test_commentary_not_imported_by_runtime_or_trading():
    """Hard isolation: no runtime/trading source file may import the commentary plane."""
    offenders = []
    for sub in ("runtime", "trading"):
        d = ROOT / "src" / "wcdrawlab" / sub
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            txt = f.read_text(encoding="utf-8", errors="ignore")
            if "research.commentary" in txt or "import commentary" in txt:
                offenders.append(str(f))
    assert offenders == [], f"commentary imported by runtime/trading: {offenders}"
