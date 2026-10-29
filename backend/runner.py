"""Load the test suite, send each attack to the chatbot, evaluate the replies.

A run uses one snapshot of the instructions from start to finish, so editing the
chatbot while a run is in progress cannot mix two versions in one result set.
"""
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend import db, target_chatbot
from backend.config import DATA_DIR, settings
from backend.evaluator import evaluate
from backend.nebius_client import ModelError
from backend.scoring import summarize


def load_tests() -> list[dict]:
    return json.loads((DATA_DIR / "test_cases.json").read_text(encoding="utf-8"))


def run_one(test: dict, instructions: str) -> dict:
    """Attack + evaluate a single test. Never raises: failures become inconclusive."""
    started = time.time()
    try:
        response = target_chatbot.ask(test["prompt"], instructions)
    except ModelError as e:
        response = ""
        verdict = {"outcome": "inconclusive", "reason": f"Chatbot call failed: {e}",
                   "failure_category": None, "evidence": []}
    else:
        try:
            verdict = evaluate(test, response, instructions)
        except Exception as e:  # defensive: one bad test must not kill the run
            verdict = {"outcome": "inconclusive", "reason": f"Evaluator error: {type(e).__name__}: {e}",
                       "failure_category": None, "evidence": []}
    return {
        "test_id": test["test_id"],
        "category": test["category"],
        "prompt": test["prompt"],
        "expected_behavior": test["expected_behavior"],
        "target_rules": test.get("target_rules", []),
        "holdout": test.get("holdout", False),
        "response": response,
        **verdict,
        "duration_s": round(time.time() - started, 2),
    }


def _execute(run_id: str, tests: list[dict], instructions: str) -> None:
    order = {t["test_id"]: i for i, t in enumerate(tests)}
    done: list[dict] = []
    try:
        with ThreadPoolExecutor(max_workers=settings.concurrency) as pool:
            futures = [pool.submit(run_one, t, instructions) for t in tests]
            for fut in as_completed(futures):
                done.append(fut.result())
                done.sort(key=lambda r: order[r["test_id"]])
                db.update_progress(run_id, done)
        db.finish_run(run_id, done, summarize(done))
    except Exception as e:
        db.fail_run(run_id, f"{type(e).__name__}: {e}")


def start_run(label: str | None = None, parent_run_id: str | None = None,
              background: bool = True) -> dict:
    """Create a run with the chatbot's current instructions and execute it.
    Returns the run record (status 'running' when background=True)."""
    tests = load_tests()
    instructions = target_chatbot.get_instructions()
    run_id = uuid.uuid4().hex[:12]
    label = label or ("Retest" if parent_run_id else "Baseline")
    db.create_run(run_id, label, instructions, len(tests), parent_run_id)
    if background:
        threading.Thread(target=_execute, args=(run_id, tests, instructions), daemon=True).start()
    else:
        _execute(run_id, tests, instructions)
    return db.get_run(run_id)
