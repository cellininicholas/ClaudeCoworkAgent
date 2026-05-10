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
echo "Default provider is 'cowork' — no API key needed. The Cowork session itself"
echo "is the LLM. To use Anthropic or OpenAI directly instead, edit .env."
echo
echo "Next steps:"
echo "  1. Start the dashboard:        .venv/bin/python scripts/serve.py"
echo "       → http://localhost:8787"
echo "  2. Edit your profile at:       http://localhost:8787/profile"
echo "  3. Run one cycle:"
echo "       Cowork mode:  type  /cycle  in a Claude Cowork session in this folder"
echo "       API mode:     .venv/bin/python scripts/run_all.py"
echo "  4. Wire up the scheduled task: see docs/cowork-setup.md (or type /setup)"
