# Event-Process Intelligence V1 — Active Collector Isolation
research_only=true experimental=true not_runtime_approved=true not_trade_eligible=true not_live_eligible=true
- Active collector WorldCupShadowCollector: checkout C:/Users/Mahyar/worldcup_draw_model_lab_FINAL, branch
  v1-5-prospective-operations @ dc73318, task State=Ready, WorkingDirectory=the MAIN checkout (NOT this
  research worktree), KALSHI_ENABLE_LIVE_TRADING=false, TRADING_MODE=paper. Collector uses The Odds API only.
- This program runs ONLY in worktree C:/Users/Mahyar/worldcup-event-process-intelligence (branch
  event-process-intelligence-v1, off tag dynamic-inplay-intelligence-v1). Task WorldCupEventProcessResearchRun
  runs only from here. No API-Football, no Odds API, no secrets. Phase 1 uses ONLY official StatsBomb Open Data
  (github.com/statsbomb/open-data raw) — no mirror/scrape/paid/video/360.
- The research task cannot alter collector state (separate checkout/branch/task/run dir). Collector is never
  read as a dependency. B1, frozen M2, M1-M5, candidate.py, approved_models.yaml, trading/Kalshi/risk/.env: untouched.
