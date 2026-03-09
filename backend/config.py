"""App configuration."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATASETS_DIR = DATA_DIR / "datasets"
DB_PATH = DATA_DIR / "app.db"
DB_URL = f"sqlite:///{DB_PATH}"

DATA_DIR.mkdir(exist_ok=True)
DATASETS_DIR.mkdir(exist_ok=True)

OPENAI_MODEL_TEXT = os.getenv("OPENAI_MODEL_TEXT", "gpt-4.1-mini")
OPENAI_MODEL_VISION = os.getenv("OPENAI_MODEL_VISION", "gpt-4.1")
