"""Compatibility entry point for the YuNet detector in ai_module."""

import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from ai_module.face_detection import main


if __name__ == "__main__":
    raise SystemExit(main())
