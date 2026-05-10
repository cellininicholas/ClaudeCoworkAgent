"""Run the localhost web UI.

    python scripts/serve.py        # http://localhost:8787
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from signal_brain import config, db


def main():
    db.init_db()
    print(f"Signal Brain UI → http://localhost:{config.PORT}")
    uvicorn.run("signal_brain.web:app", host="127.0.0.1", port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
