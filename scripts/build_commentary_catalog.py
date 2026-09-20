"""Phase 1: emit the commentary source catalogue (CSV + JSON) from evidence-based rows.
match_count/season are marked 'verified' or '[verify]' / 'unverified' — never fabricated."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data/reference"; REF.mkdir(parents=True, exist_ok=True)

SRC = [
 {"source_id": "soccernet_echoes", "name": "SoccerNet-Echoes", "owner": "SoccerNet consortium",
  "category": "G_broadcast_transcript", "official_ref": "arXiv:2405.07354; HF SoccerNet/SN-echoes; github.com/SoccerNet/sn-echoes",
  "access": "HuggingFace dataset + GitHub", "license": "CC BY 4.0", "coverage": "SoccerNet (top EU leagues + UCL)",
  "languages": "en,es,ru,de,fr,tr,it,pl,bs,hu", "match_count": "~471 SoccerNet [verify]",
  "granularity": "ASR segments (start/end sec)", "timestamp": "broadcast video time (sec)",
  "event_vs_pub_time": "broadcast time only; NO publication_time", "events": "none structured (ASR text)",
  "lineups": "no", "live_latency": "n/a historical", "modeling_rights": "yes (attribution)",
  "commercial_rights": "yes (CC BY 4.0)", "redistribution": "allowed w/ attribution", "price": "free",
  "reliability": "ASR + translation noise", "legal_status": "open_research_download_allowed",
  "recommendation": "weak-supervision / alignment research only; NOT live"},
 {"source_id": "soccerreplay_1988", "name": "SoccerReplay-1988 (MatchTime/MatchVoice)", "owner": "UniSoccer authors",
  "category": "D_academic_commentary", "official_ref": "arXiv:2412.01820; MatchTime paper; HF Homie0609/SoccerReplay-1988",
  "access": "HF dataset (NDA gate)", "license": "NDA, non-commercial", "coverage": "1988 matches (EU leagues/UCL)",
  "languages": "en (aligned)", "match_count": "1988 [verified]", "granularity": "~150K lines, 24 event classes",
  "timestamp": "second-level (MatchTime alignment)", "event_vs_pub_time": "event/clock time; NO original publication_time",
  "events": "24-class taxonomy", "lineups": "no", "live_latency": "n/a", "modeling_rights": "non-commercial per NDA",
  "commercial_rights": "NO", "redistribution": "prohibited", "price": "free w/ NDA", "reliability": "alignment-model timestamps",
  "legal_status": "NDA_or_manual_approval_required", "recommendation": "needs NDA acceptance (your decision); then weak-supervision/alignment only; NOT live"},
 {"source_id": "api_football", "name": "API-Football (api-sports.io)", "owner": "API-Sports", "category": "A_structured_api",
  "official_ref": "api-football.com/documentation-v3", "access": "REST API (paid Pro, already held)", "license": "commercial API terms",
  "coverage": "WC/Euros/Copa/AFCON/AsianCup/UCL/top leagues", "languages": "n/a structured", "match_count": "extensive",
  "granularity": "structured events every ~15s", "timestamp": "match minute + retrieval", "event_vs_pub_time": "retrieval_time available; NOT narrative text",
  "events": "goals/cards/subs (+stats/xG varies)", "lineups": "yes", "live_latency": "~15s", "modeling_rights": "per API terms",
  "commercial_rights": "per plan", "redistribution": "restricted", "price": "$19+/mo (held)", "reliability": "high",
  "legal_status": "API_account_required", "recommendation": "structured events (already used by collector); NOT a commentary-text source"},
 {"source_id": "sportmonks_commentary", "name": "Sportmonks Match Commentary API", "owner": "Sportmonks", "category": "C_licensed_feed",
  "official_ref": "sportmonks.com/glossary/match-commentary-api", "access": "REST API (paid)", "license": "commercial API terms",
  "coverage": "2500+ leagues incl internationals", "languages": "multi", "match_count": "extensive",
  "granularity": "narrative commentary lines + important flag", "timestamp": "match minute; API update time (verify)",
  "event_vs_pub_time": "API update time MAY serve as pub_time (verify)", "events": "linked", "lineups": "yes (add-on)",
  "live_latency": "low (live plan)", "modeling_rights": "per license", "commercial_rights": "per license", "redistribution": "restricted",
  "price": "EUR29-249/mo + add-ons", "reliability": "good", "legal_status": "commercial_license_required",
  "recommendation": "best realistic LIVE commentary route IF timestamps verify; paid account (your decision)"},
 {"source_id": "official_match_centers", "name": "FIFA/UEFA/CONMEBOL/AFC/CAF match centers", "owner": "federations",
  "category": "B_match_center", "official_ref": "official competition match-centre pages", "access": "web (no open commentary API)",
  "license": "copyright; ToS restrict automated use", "coverage": "their competitions", "languages": "multi", "match_count": "n/a",
  "granularity": "live text blog", "timestamp": "page publication time", "event_vs_pub_time": "pub time exists but ToS-restricted",
  "events": "yes", "lineups": "yes", "live_latency": "live", "modeling_rights": "NO without license", "commercial_rights": "NO",
  "redistribution": "prohibited", "price": "n/a", "reliability": "high", "legal_status": "scraping_not_permitted_or_not_verified",
  "recommendation": "do NOT scrape; license/approval required"},
 {"source_id": "news_live_blogs", "name": "Sports-news live blogs (BBC/Guardian/ESPN/etc)", "owner": "publishers",
  "category": "F_news_live_blog", "official_ref": "publisher ToS", "access": "web (ToS prohibit automated extraction)",
  "license": "copyright; often Opta-powered", "coverage": "major matches", "languages": "multi", "match_count": "n/a",
  "granularity": "narrative live text", "timestamp": "publication time", "event_vs_pub_time": "pub time exists",
  "events": "prose", "lineups": "prose", "live_latency": "live", "modeling_rights": "NO without license", "commercial_rights": "NO",
  "redistribution": "prohibited", "price": "n/a", "reliability": "high", "legal_status": "scraping_not_permitted_or_not_verified",
  "recommendation": "REJECT for automated use (copyright/ToS)"},
 {"source_id": "yallashoot_arabic", "name": "YallaShoot / Arabic commentary mirrors", "owner": "unclear",
  "category": "J_multilingual", "official_ref": "none authoritative", "access": "web (unclear/likely infringing)",
  "license": "unknown/likely unlicensed", "coverage": "varies", "languages": "ar", "match_count": "unverified",
  "granularity": "narrative", "timestamp": "unclear", "event_vs_pub_time": "unknown", "events": "prose", "lineups": "no",
  "live_latency": "unknown", "modeling_rights": "no", "commercial_rights": "no", "redistribution": "no", "price": "n/a",
  "reliability": "unknown", "legal_status": "rejected_for_project_use", "recommendation": "REJECT (unverified rights / likely infringing)"},
 {"source_id": "statsbomb_open", "name": "StatsBomb Open Data", "owner": "StatsBomb (Hudl)", "category": "E_open_repo",
  "official_ref": "github.com/statsbomb/open-data", "access": "GitHub (open)", "license": "non-commercial research + attribution",
  "coverage": "WC2018/22, Euro2020/24, AFCON2023, Copa2024, womens, some leagues", "languages": "n/a", "match_count": "~333 mens intl",
  "granularity": "structured events + xG + 360", "timestamp": "match minute/second", "event_vs_pub_time": "event time; NOT narrative/pub time",
  "events": "full + xG", "lineups": "yes", "live_latency": "n/a", "modeling_rights": "non-commercial research", "commercial_rights": "NO",
  "redistribution": "per agreement", "price": "free (open tier)", "reliability": "high", "legal_status": "noncommercial_research_only",
  "recommendation": "structured TRUTH ANCHOR for alignment (already used); not commentary text"},
]


def main():
    fields = sorted({k for s in SRC for k in s})
    with (REF / "commentary_source_catalog.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for s in SRC:
            w.writerow({k: s.get(k, "") for k in fields})
    (REF / "commentary_source_catalog.json").write_text(json.dumps(SRC, indent=2), encoding="utf-8")
    print(f"wrote {len(SRC)} sources")
    print("legal_status:", dict(Counter(s["legal_status"] for s in SRC)))


if __name__ == "__main__":
    main()
