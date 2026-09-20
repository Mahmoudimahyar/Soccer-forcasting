# SoccerNet Action-Label Acquisition Report (Phase 2, 2026-06-23)

- Source: official SoccerNet pip package (v0.1.62), `downloadGames(files=["Labels-v2.json"], split=["test"])`.
- **No password / NDA used** — labels are the open research artifact; the NDA password gates VIDEOS only.
- Acquired: **100 games (test split), 22,551 events, 17 classes**; fields gameTime, label, position(ms),
  team, visibility. **No player IDs.** No publication_time (match-clock only -> historical, never live).
- License: non-commercial research + attribution. Raw stored ONLY in gitignored
  `data/raw/soccernet_action_labels/` (0 tracked); manifest: `notes/research/soccernet_action_label_manifest.json`.
- IDs: SoccerNet game PATHS (championship/season/match) == SoccerNet-Echoes keys -> joinable (Phase 3).
- Videos/features/360: NOT downloaded (out of scope; NDA-gated; unnecessary for alignment).
- Classification: **verified_open_research_download** (confirmed empirically: labels pulled with no password).
