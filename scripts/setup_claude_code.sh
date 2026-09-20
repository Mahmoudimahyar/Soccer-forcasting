#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest -q

if [ ! -d .git ]; then
  git init
  git add .
  git commit -m "Initial World Cup probability lab with guarded runtime"
fi

echo "Setup complete. Open Claude Code in this directory and paste docs/CLAUDE_CODE_BOOTSTRAP_PROMPT.md"
