# Commentary Source Rights Audit (Phase 2)

Per-source use-type matrix is in `schemas/commentary_source_rights_v1.yaml`. Summary of what each use
means and the cross-source disposition.

## Use-type definitions
- **store_raw_text**: keep the original commentary string (gitignored only; never in Git).
- **store_hashed_text**: keep only a content hash (provenance without retaining text).
- **store_derived_event_labels**: keep extracted labels (event type/team/player), not the prose.
- **train_model_on_text / evaluate_model_on_text**: use text to fit / score a model.
- **show_text_in_product**: display commentary to a user.
- **use_text_as_live_model_input**: feed commentary to a live prediction (ALSO needs the causal gate).
- **redistribute_samples / commercial_use**: share samples / any commercial use.

## Disposition matrix (summary)
| source | download | derived labels | train/eval | live input | redistribute | commercial |
|---|---|---|---|---|---|---|
| soccernet_echoes (CC BY 4.0) | yes | yes | yes | NO (no pub_time) | yes | yes |
| soccerreplay_1988 (NDA) | only after NDA | no* | no* | no | no | no |
| sportmonks_commentary (paid) | only after license | no* | no* | maybe (verify ts) | no | per license |
| statsbomb_open | yes | yes | n/a (structured) | no | per agreement | no |
| api_football | n/a | yes | n/a (structured) | no | no | per plan |
| official_match_centers | NO | no | no | no | no | no |
| news_live_blogs | NO | no | no | no | no | no |
| yallashoot_arabic | NO (rejected) | no | no | no | no | no |
(*unlocks only after the stated external approval.)

## Conclusion
Only **SoccerNet-Echoes** is usable now (open, attribution) — and only for **historical / weak-supervision /
alignment**, never live. Everything richer requires an NDA (SoccerReplay-1988) or a paid license
(Sportmonks). No source is both rights-clear AND live-eligible today.
