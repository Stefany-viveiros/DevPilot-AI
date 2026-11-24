import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "backend" / "data" / "devpilot.db"
DATABASE_URL = os.getenv("DEVPILOT_DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}")
APP_NAME = "DevPilot AI"
APP_VERSION = "0.1.0"
