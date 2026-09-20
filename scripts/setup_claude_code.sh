#!/usr/bin/env bash
# Optional convenience bootstrap. Run from the REPOSITORY ROOT:  bash scripts/setup_claude_code.sh
set -euo pipefail

python -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
pip install -r requirements.txt
pip install -e .
pytest -q

echo "Setup complete. See QUICKSTART.md. For the AI-assisted workflow, see docs/ai-workflow/README.md."
