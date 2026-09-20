Next: build domain-transfer pipeline + 14-job controller; install+start WorldCupHierarchicalDomainTransferRun; run to terminal; auto-finalize.

## 2026-06-29 — EXACT RESUME (Phase A, PHASE_A_REPAIRING)
Club-root path defect repaired across 2 of 3 builders (inventory + transfer); VERIFIED: build_club_rows(5)->726,
inventory domains.club.events_materialized=669. REMAINING RECOVERABLE DEFECT (precisely diagnosed):
- scripts/audit_domain_feature_overlap.py PROFILES only international (258); for club it merely reads the
  inventory `events_materialized` FLAG and never loads/profiles the 669 club event distributions, so SMD/
  variance-ratio/overlap/Wasserstein/out-of-support/transfer-risk have no club distribution -> every feature
  stays insufficient_data -> JOB4 stability all insufficient -> JOB5 stable-feature filter drops all club rows
  -> 0 club training rows -> T2-T7 club-transfer arms are data_insufficient (the central question unexercised).
EXACT REPAIR: implement club feature-profiling in audit_domain_feature_overlap.py (load club events via
DR.get_root('statsbomb_raw_event_process')/'event_process_auxiliary' through the SAME engine + decision-minute
profiling used for international; compute real cross-domain stats; classify features; TRAINING-folds only) +
add the >=12 club-separation regression tests (A3) + ensure DND.build_all_fold_rows retains club rows whose
features are stable_transferable. Then reset JOB3-14 and re-run the durable task (Windows task survives session
restarts; Bash background does NOT). Verify transfer_dataset_v1.csv has nonzero club rows before JOB6.
ENVIRONMENT NOTE: the Claude session/process has cycled repeatedly this run, killing every multi-minute Bash
background job; the durable Windows task + watchdog are the only reliable execution path here.
