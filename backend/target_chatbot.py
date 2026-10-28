"""The sample chatbot under test. Its instructions can be replaced (the "apply fix" step)."""
import json

from backend import db
from backend.config import DATA_DIR
from backend.nebius_client import chat

_RULES = json.loads((DATA_DIR / "chatbot_rules.json").read_text(encoding="utf-8"))
_instructions = _RULES["default_instructions"]
_STATE_KEY = "chatbot_instructions"


def get_config() -> dict:
    return {
        "name": _RULES["name"],
        "description": _RULES["description"],
        "rules": _RULES["rules"],
        "protected_values": [{"id": p["id"], "label": p["label"]} for p in _RULES["protected_values"]],
        "instructions": _instructions,
        "is_default": _instructions == _RULES["default_instructions"],
    }


def protected_values() -> list[dict]:
    return _RULES["protected_values"]


def rules() -> list[dict]:
    return _RULES["rules"]


def get_instructions() -> str:
    return _instructions


def restore() -> None:
    """Load instructions saved by a previous server session (call after db.init())."""
    global _instructions
    _instructions = db.get_state(_STATE_KEY) or _RULES["default_instructions"]


def set_instructions(text: str) -> None:
    global _instructions
    _instructions = text
    db.set_state(_STATE_KEY, None if text == _RULES["default_instructions"] else text)


def reset_instructions() -> None:
    set_instructions(_RULES["default_instructions"])


def ask(user_message: str, instructions: str | None = None) -> str:
    """One turn with the chatbot. Pass `instructions` to pin a snapshot for a run."""
    return chat([
        {"role": "system", "content": instructions if instructions is not None else _instructions},
        {"role": "user", "content": user_message},
    ])
