"""FastAPI app. Day 1: health, chatbot config, and a single-attack endpoint.
Runs, suggestions and compare endpoints arrive on Days 2-5 (see docs/api_contract.md)."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import target_chatbot
from backend.config import settings
from backend.evaluator import evaluate
from backend.nebius_client import ModelError

app = FastAPI(title="AgentShield API", version="0.1.0")
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/api/health")
def health():
    return {"status": "ok", "model": settings.model, "judge_model": settings.judge_model,
            "mock": settings.mock}


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


class AttackIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    expected_behavior: str = "Follow all rules and refuse the attack."


@app.post("/api/debug/attack")
def single_attack(body: AttackIn):
    """Day 1 helper: send one attack and evaluate it. Not part of the final contract."""
    test = {"test_id": "adhoc", "category": "adhoc", "prompt": body.prompt,
            "expected_behavior": body.expected_behavior, "target_rules": []}
    instructions = target_chatbot.get_instructions()
    try:
        response = target_chatbot.ask(body.prompt, instructions)
    except ModelError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {**test, "response": response, **evaluate(test, response, instructions)}


# Serve Member 2's frontend at "/" once frontend/index.html exists.
if (FRONTEND / "index.html").exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND / "index.html")
