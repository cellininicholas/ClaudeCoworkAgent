#!/usr/bin/env bash
# Signal Brain — one-shot setup
set -euo pipefail

cd "$(dirname "$0")"

echo "→ Creating virtualenv (.venv)"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ Installing dependencies"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

if [[ ! -f .env ]]; then
  echo "→ Creating .env from .env.example (edit it to add ANTHROPIC_API_KEY)"
  cp .env.example .env
fi

echo "→ Initialising SQLite DB + default sources"
python scripts/init_db.py

echo
echo "Setup complete."
echo
echo "Next steps:"
echo "  1. Add your ANTHROPIC_API_KEY to .env"
echo "  2. Run the UI:                 python scripts/serve.py"
echo "  3. Edit your profile at:       http://localhost:8765/profile"
echo "  4. Run one full cycle:         python scripts/run_all.py"
echo "  5. Wire it up in Cowork:       see docs/cowork-setup.md"
