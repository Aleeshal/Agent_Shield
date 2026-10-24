"""Day 1 proof of concept: call the model, run attacks, evaluate them.

Usage (from the project root, venv active):
    python -m scripts.smoke_test            # first test only
    python -m scripts.smoke_test --all      # every test in test_cases.json
"""
import json
import sys
import time

from backend import target_chatbot
from backend.config import DATA_DIR, settings
from backend.evaluator import evaluate
from backend.nebius_client import ModelError, chat


def main() -> None:
    print(f"Base URL : {settings.base_url}")
    print(f"Model    : {settings.model}   Judge: {settings.judge_model}")
    print(f"Mock mode: {settings.mock}\n")

    # Step 1: can we reach the model at all?
    try:
        t = time.time()
        reply = chat([{"role": "user", "content": "Reply with exactly: pong"}], max_tokens=20)
        print(f"[1] Model reachable ({time.time() - t:.1f}s): {reply!r}\n")
    except ModelError as e:
        print(f"[1] FAILED to call the model: {e}")
        print("    Check NEBIUS_API_KEY, NEBIUS_BASE_URL and NEBIUS_MODEL in .env.")
        sys.exit(1)

    # Step 2: run attacks and evaluate
    tests = json.loads((DATA_DIR / "test_cases.json").read_text(encoding="utf-8"))
    if "--all" not in sys.argv:
        tests = tests[:1]
    instructions = target_chatbot.get_instructions()
    counts: dict[str, int] = {}
    for test in tests:
        try:
            response = target_chatbot.ask(test["prompt"], instructions)
            result = evaluate(test, response, instructions)
        except ModelError as e:
            response, result = "", {"outcome": "inconclusive", "reason": f"Chatbot call failed: {e}"}
        counts[result["outcome"]] = counts.get(result["outcome"], 0) + 1
        print(f"--- {test['test_id']} ({test['category']}) -> {result['outcome'].upper()}")
        print(f"Prompt  : {test['prompt'][:100]}")
        print(f"Reply   : {response[:200]!r}")
        print(f"Reason  : {result['reason']}\n")

    print("Summary:", counts)


if __name__ == "__main__":
    main()
