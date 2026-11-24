import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "backend" / "data" / "devpilot.db"
DATABASE_URL = os.getenv("DEVPILOT_DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}")
WORKSPACE_DIR = Path(os.getenv("DEVPILOT_WORKSPACE_PATH", str(PROJECT_ROOT / "workspace"))).resolve()
APP_NAME = "DevPilot AI"
APP_VERSION = "0.3.0"
MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_EXTRACTED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_FILES = 2000
MAX_SINGLE_FILE_BYTES = 10 * 1024 * 1024
