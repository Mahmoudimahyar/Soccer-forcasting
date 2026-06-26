"""Phase 3 licensed-event framework tests. Synthetic fixtures only; no network, no credentials."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.licensed_events import (mock_provider as MP, availability as AV,  # noqa: E402
                                               reconciliation as R, registry as REG, provider_interface as PI)


def test_capability_gating_drops_unsupported_fields():
    # provider without xg/shot_locations capability must NOT populate them even if raw carries them
    p = MP.MockProvider(caps={"player_ids": True, "cards": True, "publication_time": True})
    ev = p.normalize_event(MP.fixture_full_event())
    assert ev.xg is None and ev.shot_location is None
    p2 = MP.MockProvider()  # full caps
    ev2 = p2.normalize_event(MP.fixture_full_event())
    assert ev2.xg == 0.42 and ev2.shot_location == {"x": 0.9, "y": 0.5}


def test_publication_time_requirement_and_no_future_leak():
    assert AV.live_publication_safe("2026-06-20T19:05:00+00:00", "2026-06-20T19:05:10+00:00") is True
    assert AV.live_publication_safe("2026-06-20T19:05:30+00:00", "2026-06-20T19:05:10+00:00") is False  # future
    assert AV.live_publication_safe(None, "2026-06-20T19:05:10+00:00") is False  # unknown -> fail closed


def test_fail_closed_without_publication_time():
    hist = MP.MockProvider(availability={"has_publication_time": False, "has_event_time": True,
                                         "historical_available": True, "live_available": False})
    ev = hist.normalize_event(MP.fixture_historical_only())
    assert ev.causal_eligibility == "historical_only"
    assert AV.is_live_eligible(ev) is False


def test_source_hash_traceability():
    ev = MP.MockProvider().normalize_event(MP.fixture_full_event())
    assert ev.source_snapshot_hash == "snap1"
    raw = MP.fixture_full_event(); raw.pop("source_snapshot_hash")
    ev2 = MP.MockProvider().normalize_event(raw)
    assert ev2.source_snapshot_hash and len(ev2.source_snapshot_hash) == 64  # derived hash present


def test_player_id_preserved_never_invented():
    ev = MP.MockProvider().normalize_event(MP.fixture_full_event())
    assert ev.player_id == "P10"
    miss = MP.MockProvider().normalize_event(MP.fixture_missing_player_id())
    assert miss.player_id is None  # NOT invented


def test_no_invented_fields_on_incomplete():
    ev = MP.MockProvider().normalize_event(MP.fixture_incomplete_match())
    assert ev.player_id is None and ev.match_clock_s is None and ev.period == "unknown"


def test_correction_idempotency():
    p = MP.MockProvider()
    evs = [p.normalize_event(MP.fixture_card_correction()), p.normalize_event(MP.fixture_card_correction())]
    once = R.apply_corrections(evs)
    twice = R.apply_corrections(once)
    assert once == twice


def test_var_retraction_removed():
    p = MP.MockProvider()
    evs = [p.normalize_event(MP.fixture_full_event()), p.normalize_event(MP.fixture_var_reversal())]
    out = R.apply_corrections(evs)
    assert all(e.correction_status != "retracted" for e in out)


def test_score_reconciliation_owngoal_and_shootout():
    p = MP.MockProvider()
    home_goal = p.normalize_event(MP.fixture_full_event())            # HOME scores
    og = p.normalize_event(MP.fixture_full_event()); og.event_type = "own_goal"; og.team_id = "AWAY"  # AWAY OG -> HOME
    so = p.normalize_event(MP.fixture_full_event()); so.period = "shootout"; so.team_id = "AWAY"       # ignored
    h, a = R.reconcile_score([home_goal, og, so])
    assert (h, a) == (2, 0)


def test_cross_provider_reconcile_agree_and_conflict():
    pa, pb = MP.MockProvider(), MP.MockProvider()
    a = pa.normalize_event(MP.fixture_full_event())
    b_agree = pb.normalize_event(MP.fixture_full_event())
    res = R.cross_provider_reconcile([a], [b_agree])
    assert len(res["agree"]) == 1 and not res["conflict"]
    b_conf = pb.normalize_event(MP.fixture_conflicting_event())  # same goal, different scorer
    res2 = R.cross_provider_reconcile([a], [b_conf])
    assert len(res2["conflict"]) == 1


def test_deterministic_normalization():
    a = MP.MockProvider().normalize_event(MP.fixture_full_event())
    b = MP.MockProvider().normalize_event(MP.fixture_full_event())
    assert a == b


def test_registry_refuses_runtime_or_trade_eligible():
    class Bad(PI.ProviderAdapter):
        provider_name = "bad"; RUNTIME_ELIGIBLE = True
        def declare_capabilities(self): ...
        def declare_availability(self): return {}
    try:
        REG.register(Bad); raised = False
    except ValueError:
        raised = True
    assert raised
    assert REG.is_runtime_eligible("mock_provider") is False


def test_not_imported_by_runtime_or_trading():
    offenders = []
    for sub in ("runtime", "trading"):
        d = ROOT / "src" / "wcdrawlab" / sub
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            t = f.read_text(encoding="utf-8", errors="ignore")
            if "licensed_events" in t:
                offenders.append(str(f))
    assert offenders == []
