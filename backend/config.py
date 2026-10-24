"""Settings read from .env. Import `settings` everywhere else."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = Path(__file__).resolve().parent / "data"


class Settings:
    api_key: str = os.getenv("NEBIUS_API_KEY", "")
    base_url: str = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
    model: str = os.getenv("NEBIUS_MODEL", "nvidia/nemotron-3-super-120b-a12b")
    judge_model: str = os.getenv("NEBIUS_JUDGE_MODEL") or os.getenv(
        "NEBIUS_MODEL", "nvidia/nemotron-3-super-120b-a12b"
    )
    mock: bool = os.getenv("NEBIUS_MOCK", "0") == "1"
    timeout_s: float = float(os.getenv("NEBIUS_TIMEOUT", "60"))


settings = Settings()
