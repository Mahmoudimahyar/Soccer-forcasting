# SoccerNet Match-Mapping Quality (Phase 3, real data)
- Echoes corpus matches (whisper_v1): 529; (whisper_v1_en): 367. Acquired label matches: 385.
- Join: exact SoccerNet game-path after stripping Echoes trailing half-number. **373 exact joins**
  (whisper_v1) / **254** (whisper_v1_en); 0 normalized/ambiguous/override needed; **0 label-side collisions**.
- Mapping success rate = exact joins / echoes-matches-with-a-label-counterpart = 100% of intersecting
  games (no fuzzy matching used). Non-joined echoes games = simply not in the acquired label splits.
- Determinism: mapper is pure-function; 8 synthetic mapping tests pass.
