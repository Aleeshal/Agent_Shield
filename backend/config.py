"""Settings read from .env. Import `settings` everywhere else.

No values need editing here: set them in .env (local) or the host's environment variables
(deployed). The only required one is NEBIUS_API_KEY. See docs/SETUP_AND_DEPLOYMENT.md."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"


def _env(name: str, default: str = "") -> str:
    """Like os.getenv, but an empty value (e.g. `KEY=` copied from .env.example) means the default."""
    return (os.getenv(name) or "").strip() or default


def _num(name: str, default: float, cast=float):
    try:
        return cast(_env(name, str(default)))
    except ValueError:
        return default


class Settings:
    api_key: str = _env("NEBIUS_API_KEY")
    base_url: str = _env("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
    model: str = _env("NEBIUS_MODEL", DEFAULT_MODEL)
    judge_model: str = _env("NEBIUS_JUDGE_MODEL") or model
    mock: bool = _env("NEBIUS_MOCK", "0") == "1"
    timeout_s: float = _num("NEBIUS_TIMEOUT", 60.0)
    # Ask reasoning models to answer directly (sent as chat_template_kwargs.enable_thinking=false)
    disable_thinking: bool = _env("NEBIUS_DISABLE_THINKING", "0") == "1"
    # How many tests run in parallel. Lower it if you hit rate limits.
    concurrency: int = max(1, _num("AGENTSHIELD_CONCURRENCY", 4, int))
    db_path: Path = Path(_env("AGENTSHIELD_DB", str(ROOT / "agentshield.db")))


settings = Settings()
