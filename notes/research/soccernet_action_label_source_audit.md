# SoccerNet Action-Label Source Audit (Phase 1, 2026-06-23)

Official sources only (SoccerNet GitHub, pip package, dataset pages, papers).

## Finding
- **Action-spotting labels** = `Labels-v2.json`, **17 action classes**, per game, across 500 broadcast
  games. Distributed via the official **`SoccerNet` pip package** (`SoccerNetDownloader.downloadGames(
  files=["Labels-v2.json"], split=[...])`). Refs: pypi.org/project/SoccerNet, github.com/SoccerNet/sn-spotting.
- **NDA/password gate applies to the VIDEOS** (and some feature files), NOT to the labels: "to download
  the videos you must fill an NDA to get the password." Labels/annotations are the open research artifact.
- Game IDs are SoccerNet game PATHS (championship/season/match) — the SAME keys SoccerNet-Echoes uses ->
  **exact overlap if both cover the same games**.

## Label fields (Labels-v2.json, per official schema)
- gameTime (period + match clock MM:SS), label (one of 17 classes incl. goal, cards, substitution,
  corner, shots-on/off-target, penalty, offside, kick-off, etc.), team (home/away), visibility
  (visible/not shown). **No player IDs** in v2 action labels; **event timestamp = match clock** (no
  publication time — consistent with the causal rule: historical only).

## License / rights
- SoccerNet data is a **non-commercial research** dataset (academic challenges). Labels: research
  download + local retention + derived labels + aggregate-metric publication are standard academic use;
  redistribution of raw files is restricted; **attribution required**; videos NDA-gated (not needed here).
- Classification: **verified_open_research_download (labels)** pending empirical confirmation that the
  label download needs no password (resolved in Phase 2 by attempting an official, no-password pull).

## Overlap with SoccerNet-Echoes
- Structural: exact (same game paths). Actual overlap count depends on which games are in both -> measured
  in Phase 3 once labels for the Echoes sample games are pulled.
