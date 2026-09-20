- 2026-06-26T18:00:01.366663+00:00 state=RUNNING main_task=Running hb_age=629.0935523509979 collector=dc73318(ok) violations=none action=observe
- 2026-06-26T18:01:02.854563+00:00 state=RUNNING main_task=Running hb_age=690.5881953239441 collector=dc73318(ok) violations=none action=healthy: do nothing (long job in progress; hb_age=690s)
- 2026-06-26T18:16:05.871080+00:00 state=RUNNING main_task=Running hb_age=1593.4055199623108 collector=dc73318(ok) violations=none action=healthy: do nothing (long job in progress; hb_age=1593s)
- 2026-06-26T18:31:05.662761+00:00 state=RUNNING main_task=Running hb_age=2493.379380464554 collector=dc73318(ok) violations=none action=healthy: do nothing (long job in progress; hb_age=2493s)
- 2026-06-26T18:46:05.747534+00:00 state=RUNNING main_task=Running hb_age=3393.389327764511 collector=dc73318(ok) violations=none action=healthy: do nothing (long job in progress; hb_age=3393s)
- 2026-06-26T19:01:05.913492+00:00 state=WAITING_FOR_API_QUOTA main_task=Ready hb_age=195.6418571472168 collector=dc73318(ok) violations=none action=ensure daily resume enabled (resume_task=Ready); do NOT force resume before quota window
- 2026-06-26T19:16:05.673268+00:00 state=RUNNING main_task=Running hb_age=18.54650616645813 collector=dc73318(ok) violations=none action=healthy: do nothing (no second worker)
- 2026-06-26T19:31:05.709082+00:00 state=RUNNING main_task=Running hb_age=918.5517454147339 collector=dc73318(ok) violations=none action=healthy: do nothing (long job in progress; hb_age=918s)
- 2026-06-26T19:45:05.931588+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=509.89700531959534 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T19:46:05.936264+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=569.8803915977478 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart

## 2026-06-26 — adversarial audit of corpus-completion claim (ultracode workflow, read-only)
Event: API-Football corpus reached done=2000/2000 with the new dynamic quota reserve (881 of 1637 budget used;
quota_remaining_after=1013 >> reserve 200). A 6-agent read-only verification workflow was run BEFORE trusting
the gate.
- FINDING (caught, not shipped): the 100% claim over-reported on a SINGLE root. done-list had 2000 ids but the
  canonical root held events+lineups for only 1940; 60 ids (the prior 60-fixture pull, 592xxx block) were
  backed only in the registered read-only prior root. All 1940 canonical payloads were valid (0 errors / 0
  empty / 0 HTML). manifest-coverage PASS (done==manifest, no substitution). integrity-isolation PASS (raw
  0-tracked + gitignored; collector dc73318 unchanged; no key leak). 
- FIX (honest, no API re-download): consolidated the 60 prior payloads (120 files) into the canonical root via
  LOCAL COPY -> canonical now self-contained (2000/2000 raw-backed, missing=[]). Completion gate is now measured
  by ACTUAL raw-backed coverage across registered roots (corpus_coverage.py), NOT done-list length; 3 regression
  tests added. corpus_coverage_ledger.json records before/after.
- STATE: run finished its queue (JOB2 corpus complete; JOB3 reconcile complete 960 fixtures, sendings_off=128;
  JOB4 StatsBomb skipped 23%<90%; JOB5-8 honest deferred skips; JOB9 ledger). run_state set to
  WAITING_FOR_SOURCE (StatsBomb is the binding incomplete source). Watchdog patched to treat WAITING_FOR_SOURCE
  as a legitimate non-running pause (NO restart-loop). No completion tag. Collector untouched.
- 2026-06-26T20:01:05.952935+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=1469.8794958591461 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T20:16:05.938746+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=2369.871495962143 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T20:31:06.023715+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=3269.882489681244 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T20:46:05.954354+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=4169.88267159462 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T21:01:05.971394+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=5069.91042637825 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T21:16:06.009274+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=5969.943002939224 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T21:31:05.999555+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=6869.924413204193 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T21:46:06.073589+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=7769.9389526844025 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T22:01:06.029082+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=8669.955476284027 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T22:16:06.025463+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=9569.966787576675 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T22:31:06.019123+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=10469.956694364548 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T22:46:06.046123+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=11369.972790002823 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T23:01:06.138004+00:00 state=WAITING_FOR_SOURCE main_task=Ready hb_age=12269.985968589783 collector=dc73318(ok) violations=none action=observe: corpus complete, waiting on external source (StatsBomb); no restart
- 2026-06-26T23:10:31.064470+00:00 state=RUNNING main_task=Ready hb_age=72.24049043655396 collector=dc73318(ok) violations=none action=observe

## 2026-06-26 — StatsBomb source reactivated; cache + xG join COMPLETE (two named events)
- Official-source availability probe (approved StatsBomb Open Data, no scrape/mirror/paid/video/360): 5/5 missing
  exact-bridge matches resolved with xG fields -> WAITING_FOR_SOURCE -> RUNNING. Same run id truth_20260626_134931.
- NAMED EVENT: StatsBomb cache 258/258 valid exact-bridge (100%, gate ceil(0.90*258)=233 MET), all xG fields.
  <=4 concurrent, resumable, append-only manifest, canonical root via registry. Audit: statsbomb_cache_audit.json.
- NAMED EVENT: xG snapshot join NONZERO (was 0): 4386 audited xG-eligible regulation international snapshots over
  258 exact-bridged matches; causal, leakage-tested (5 tests). Audit: xg_snapshot_join_audit.json.
- Verified: 0 API-Football calls, 0 Odds API calls, StatsBomb raw increased only under canonical gitignored root,
  collector dc73318 untouched, 279 tests pass. Watchdog crash-detect hardened (requires a stuck 'running' job).
- Remaining (modeling phase, buildable): dynamic dataset rebuild + preregistered evaluations. No model trained;
  NO completion tag; no incomplete tag.
- 2026-06-26T23:16:06.042700+00:00 state=RUNNING main_task=Ready hb_age=407.1927740573883 collector=dc73318(ok) violations=none action=observe
- 2026-06-26T23:31:06.079604+00:00 state=RUNNING main_task=Ready hb_age=1307.2006149291992 collector=dc73318(ok) violations=none action=observe
- 2026-06-26T23:46:06.103207+00:00 state=RUNNING main_task=Ready hb_age=2207.1986651420593 collector=dc73318(ok) violations=none action=observe
- 2026-06-27T00:01:06.075842+00:00 state=RUNNING main_task=Ready hb_age=3107.2165060043335 collector=dc73318(ok) violations=none action=observe
- 2026-06-27T00:16:06.079699+00:00 state=RUNNING_MODEL_PHASE main_task=Ready hb_age=94.0773663520813 collector=dc73318(ok) violations=none action=observe
