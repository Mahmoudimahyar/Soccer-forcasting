# Hierarchical Transfer — Club-Root Repair (2026-06-28)
research_only. DEFECT: the 669 club event JSONs (event-process program) were not registered as an explicit
read-only source root; transfer builders resolved club events only from this worktree's empty
statsbomb_raw/event_process_auxiliary -> club_materialized=0 -> feature-overlap audit returned stable_transferable=0
and the transfer dataset had 0 club training rows (NOT a real absence — files exist; manifest↔file id overlap 669/669).
REPAIR: registered data_roots root `statsbomb_raw_event_process` = C:/Users/Mahyar/worldcup-event-process-intelligence/
data/raw/statsbomb_open (read-only, existing local data; NOT re-acquired) + added it to the builders' club resolution.
VERIFIED: inventory club_materialized=669; build_club_rows(5)->726 real club rows status=ok. No raw file changed; no
external source called. before=0 after=669. The durable controller (JOB4) rebuilds the club-inclusive transfer dataset.
