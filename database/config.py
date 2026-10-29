"""Load optional local database settings without overriding process variables."""

import os
from pathlib import Path


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_local_environment():
    """Read simple KEY=VALUE settings from the ignored project .env file."""
    if not ENV_FILE.is_file():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key.startswith("ATTENDANCE_"):
            os.environ.setdefault(key, value)
