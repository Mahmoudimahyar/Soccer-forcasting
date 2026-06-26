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
