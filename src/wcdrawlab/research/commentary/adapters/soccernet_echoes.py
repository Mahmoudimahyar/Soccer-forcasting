"""SoccerNet-Echoes adapter (CC BY 4.0). Normalizes ASR segments {start,end,text,language} into the
canonical contract. CRITICAL: SoccerNet-Echoes carries BROADCAST time only (no publication_time) ->
every record is historical_weak_supervision_only and NEVER live-eligible. research_only."""
from __future__ import annotations
from ..contracts import CommentaryRecord
from ..normalization import normalize_text, content_hash
from ..quality import text_quality_status

SOURCE_ID = "soccernet_echoes"
RIGHTS = "open_research_download_allowed"


def to_records(segments, *, canonical_match_id, language, retrieval_time_utc):
    """segments: iterable of {start_time, end_time, text}. Fail-closed on missing timing semantics:
    publication_time is unknown by construction -> historical_weak_supervision_only."""
    out = []
    for i, seg in enumerate(segments):
        text = seg.get("text")
        rec = CommentaryRecord(
            canonical_commentary_id=f"{SOURCE_ID}:{canonical_match_id}:{i}",
            source_id=SOURCE_ID, canonical_match_id=canonical_match_id, language=language,
            rights_classification=RIGHTS, source_content_hash=content_hash(text),
            match_clock_second=int(seg.get("start_time")) if seg.get("start_time") is not None else None,
            commentary_time_as_reported=str(seg.get("start_time")),
            publication_time_utc_if_known=None,            # broadcast time only -> unknown pub time
            retrieval_time_utc=retrieval_time_utc,
            normalized_text=normalize_text(text), text_quality_status=text_quality_status(text),
            causal_eligibility_status="historical_weak_supervision_only",
            source_order_index=i, parser_version="soccernet_echoes_adapter_v1",
            raw_text_reference_only="(gitignored raw store)")
        out.append(rec)
    return out
