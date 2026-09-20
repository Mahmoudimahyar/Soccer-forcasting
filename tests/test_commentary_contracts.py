"""Phase 3 commentary contract tests. SYNTHETIC text only (no copyrighted commentary)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wcdrawlab.research.commentary import contracts, availability, normalization, entity_resolution, quality, alignment  # noqa: E402

SYN = "Goal for the home side, scored by Player Seven"  # synthetic, authored here


def _rec(**kw):
    base = dict(canonical_commentary_id="c1", source_id="soccernet_echoes", linked_event_type="goal")
    base.update(kw)
    return contracts.CommentaryRecord(**base)


def test_event_time_vs_publication_time_live_rule():
    # published before decision -> live-safe; published after -> NOT
    assert availability.live_publication_safe("2026-06-24T16:00:00+00:00", "2026-06-24T16:30:00+00:00") is True
    assert availability.live_publication_safe("2026-06-24T17:00:00+00:00", "2026-06-24T16:30:00+00:00") is False


def test_unknown_publication_time_never_live():
    assert availability.live_publication_safe(None, "2026-06-24T16:30:00+00:00") is False
    r = _rec(event_time_utc_if_known="2026-06-24T16:10:00+00:00", publication_time_utc_if_known=None)
    assert availability.attach_eligibility(r, rights_ok=True) == "historical_weak_supervision_only"


def test_delay_safety_margin():
    # pub 16:29:50, decision 16:30:00, safety lag 30s -> 16:30:20 > decision -> NOT safe
    assert availability.live_publication_safe("2026-06-24T16:29:50+00:00", "2026-06-24T16:30:00+00:00",
                                              safety_lag_seconds=30) is False
    # smaller lag (5s) -> 16:29:55 <= 16:30:00 -> safe
    assert availability.live_publication_safe("2026-06-24T16:29:50+00:00", "2026-06-24T16:30:00+00:00",
                                              safety_lag_seconds=5) is True


def test_rights_restricted_blocks_eligibility():
    r = _rec(publication_time_utc_if_known="2026-06-24T16:00:00+00:00")
    assert availability.attach_eligibility(r, rights_ok=False) == "rights_restricted"


def test_duplicate_and_correction_detection():
    assert quality.is_duplicate(SYN, SYN + "   ") is True
    assert quality.is_correction("Correction: no goal - ruled out by VAR") is True
    assert quality.is_correction(SYN) is False


def test_multilingual_text_preserved():
    es = "Gol del equipo local, marca el jugador siete"
    assert normalization.normalize_text("  " + es + "  ") == es  # unicode + content preserved


def test_entity_resolution_uncertainty():
    canon, conf = entity_resolution.resolve_entity("Plyr Seven", ["Player Seven", "Player Eight"])
    assert canon == "Player Seven" and 0.6 <= conf <= 1.0
    none, c0 = entity_resolution.resolve_entity("zzz", ["Player Seven"])
    assert none is None and c0 < 0.6


def test_source_hash_traceability():
    h1 = normalization.content_hash(SYN); h2 = normalization.content_hash(SYN)
    assert h1 == h2 and h1 != normalization.content_hash(SYN + "!")


def test_no_future_commentary_leakage_in_alignment():
    # a line whose publication is after the decision is timing-not-safe -> excluded from live alignment
    safe = availability.live_publication_safe("2026-06-24T16:50:00+00:00", "2026-06-24T16:30:00+00:00")
    cls = alignment.classify_alignment(0.9, timing_safe_for_live=safe)
    assert cls == "timing_not_safe_for_live_use"


def test_bad_enum_values_rejected():
    with pytest.raises(ValueError):
        _rec(linked_event_type="not_a_real_event")
    with pytest.raises(ValueError):
        _rec(causal_eligibility_status="totally_live")
