"""FastAPI app: chatbot config, test runs, suggestions, before/after comparison.
Full endpoint list and JSON shapes: docs/api_contract.md."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import db, runner, target_chatbot
from backend.config import settings
from backend.evaluator import evaluate
from backend.nebius_client import ModelError
from backend.scoring import compare
from backend.suggestions import suggest

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init()
    target_chatbot.restore()
    yield


app = FastAPI(title="AgentShield API", version="1.0.0", lifespan=lifespan)


def _run_or_404(run_id: str) -> dict:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return run


@app.get("/api/health")
def health():
    return {"status": "ok", "model": settings.model, "judge_model": settings.judge_model,
            "mock": settings.mock, "api_key_set": bool(settings.api_key)}


# ---------- chatbot ----------

@app.get("/api/chatbot")
def get_chatbot():
    return target_chatbot.get_config()


class InstructionsIn(BaseModel):
    instructions: str = Field(min_length=1, max_length=8000)


@app.put("/api/chatbot/instructions")
def update_instructions(body: InstructionsIn):
    target_chatbot.set_instructions(body.instructions)
    return target_chatbot.get_config()


@app.post("/api/chatbot/reset")
def reset_instructions():
    target_chatbot.reset_instructions()
    return target_chatbot.get_config()


# ---------- test suite and runs ----------

@app.get("/api/tests")
def list_tests():
    return runner.load_tests()


class RunIn(BaseModel):
    label: str | None = Field(default=None, max_length=80)
    parent_run_id: str | None = None


@app.post("/api/runs", status_code=202)
def create_run(body: RunIn | None = None):
    body = body or RunIn()
    if body.parent_run_id:
        _run_or_404(body.parent_run_id)
    return runner.start_run(body.label, body.parent_run_id)


@app.get("/api/runs")
def list_runs():
    return db.list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return _run_or_404(run_id)


@app.post("/api/runs/{run_id}/suggestions")
def create_suggestions(run_id: str):
    run = _run_or_404(run_id)
    if run["status"] != "done":
        raise HTTPException(status_code=409, detail="Run has not finished yet.")
    result = suggest(run)
    db.save_suggestions(run_id, result)
    return result


@app.get("/api/compare")
def compare_runs(before: str, after: str):
    b, a = _run_or_404(before), _run_or_404(after)
    if b["status"] != "done" or a["status"] != "done":
        raise HTTPException(status_code=409, detail="Both runs must be finished.")
    return compare(b, a)


# ---------- ad-hoc single attack ----------

class AttackIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    expected_behavior: str = "Follow all rules and refuse the attack."


@app.post("/api/attack")
def single_attack(body: AttackIn):
    """Send one custom attack to the chatbot and evaluate it (not saved)."""
    test = {"test_id": "adhoc", "category": "adhoc", "prompt": body.prompt,
            "expected_behavior": body.expected_behavior, "target_rules": []}
    instructions = target_chatbot.get_instructions()
    try:
        response = target_chatbot.ask(body.prompt, instructions)
    except ModelError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {**test, "response": response, **evaluate(test, response, instructions)}


# Kept so the Day 1 path still works.
app.add_api_route("/api/debug/attack", single_attack, methods=["POST"], include_in_schema=False)


# ---------- frontend ----------

if (FRONTEND / "index.html").exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND / "index.html")
