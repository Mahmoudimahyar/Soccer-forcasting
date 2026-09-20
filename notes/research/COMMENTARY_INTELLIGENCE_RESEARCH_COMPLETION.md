# Commentary Intelligence Research V1 — Completion Report (2026-06-23)

Isolated worktree `commentary-intelligence-research-v1` (off dc73318). All work research_only /
not_runtime_approved / not_trade_eligible. The live WorldCupShadowCollector was never touched.

## Active-collector isolation — CLEAN
Main checkout `worldcup_draw_model_lab_FINAL` stayed on `v1-5-prospective-operations` @ `dc73318`,
tracked-clean; task `WorldCupShadowCollector` unchanged (workdir = main). diff dc73318..HEAD = 46
ADDITIONS, zero modifications to existing files. No odds/API-Football call was triggered by this sprint.
No frozen prediction / runtime / trading / risk / Kalshi / credential touched.

## Sources reviewed / verified / rejected / approval-required
- Verified (official refs): SoccerNet-Echoes (CC BY 4.0), SoccerReplay-1988/MatchTime (NDA), API-Football
  (structured), Sportmonks Match Commentary (paid), StatsBomb open (structured).
- Rejected: news live blogs, official match-center scraping, YallaShoot/Arabic mirrors (copyright/ToS/unverified).
- Approval-required: SoccerReplay-1988 (NDA), Sportmonks (paid).

## Sample acquired
None pulled this session. SoccerNet-Echoes is acquisition-eligible (open) with the exact command +
adapter ready; bytes deferred to keep large data out. No raw copyrighted text downloaded or committed.

## Legal / rights findings
Per-source use-matrix (`schemas/commentary_source_rights_v1.yaml`): only SoccerNet-Echoes permits
download/derived-labels/train/eval now, and only historically. Everything richer needs NDA or paid license.

## Coverage + timing findings
No open, rights-clear, publication-timestamped commentary source exists for live use. Academic sets skew
to European leagues/UCL and carry broadcast/clock time only (no original publication_time). WC/continental
commentary text is paid or unavailable.

## Alignment quality findings
Provider-neutral alignment toolchain (confidence tiers, 21-class taxonomy, match-level split rule) built +
unit-tested on synthetic data; real precision/recall pending a permitted aligned sample.

## Live-use readiness
**NO source is live-eligible** (fail-closed gate). Each is rights- or timestamp-blocked. The only path to
even a delayed-live shadow test is a licensed feed (Sportmonks) after verifying publication time + lag.
Tests prove: unknown-pub-time never live; rights-uncertain never live; post-decision lines blocked; safety
lag enforced; **commentary modules are NOT imported by runtime/trading (hard isolation)**.

## Recommended source path
Now: SoccerNet-Echoes (free) for historical alignment/weak-supervision. NDA: SoccerReplay-1988 (richer).
Live: Sportmonks (paid) only after the causal gate. Never scrape news/match-center text.

## Exact next external action from you
Pick one: (a) proceed with SoccerNet-Echoes only (free, historical); (b) accept the SoccerReplay-1988 NDA;
(c) approve a paid Sportmonks trial to verify live publication timestamps.

## Exact next engineering task after approval
(a)/(b): run `commentary_sample_acquire.py --execute` then `commentary_normalize.py` + `commentary_alignment_audit.py`
for real alignment metrics, derive event labels under the rights matrix (historical weak supervision).
(c): build a Sportmonks adapter, measure publication lag, run the live-eligibility gate; only if it passes,
a delayed-live SHADOW test (never affecting live models).

## Allowed vs prohibited claims
ALLOWED: rights classifications, source landscape, contract/alignment tooling exists + tested, historical
weak-supervision readiness. PROHIBITED: any live predictive value, any market edge, any claim that
commentary improves forecasts — and commentary may not affect live predictions unless the causal gate
passes (it does not today).
