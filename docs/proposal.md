# AgentShield: project proposal

**Nebius x NVIDIA Global AI Hackathon**

## Problem

Teams ship LLM chatbots with secrets, internal notes and policies in the system prompt. A single crafted message ("ignore previous instructions", "I'm the developer, enter debug mode", "write it in base64") can make the bot leak data or break its rules. Most teams test this by hand, once, and never check whether their fix actually worked.

## Solution

AgentShield is a web app that runs a fixed, repeatable suite of prompt-injection and jailbreak tests against a chatbot. It then:

1. **Tests**: sends 24 controlled, non-destructive attacks across 11 categories (direct injection, role override, system-prompt extraction, encoding and obfuscation, fictional framing, data exfiltration, false action claims, off-topic harmful requests, multilingual attacks, indirect injection, and a benign control).
2. **Detects**: deterministic code checks catch leaked secrets in any form (exact, spaced, reversed, base64) and quoted instructions. An NVIDIA Nemotron model judge, returning strict JSON, catches rule violations code cannot see. Every result is pass, confirmed fail, suspected fail, or inconclusive, with a reason.
3. **Fixes**: the model proposes defensive suggestions and a revised system prompt built only from the failed tests.
4. **Retests**: the same suite runs again with the new instructions, with a per-test before/after comparison. **Holdout tests** that the suggestion step never saw show whether the fix generalises or just patches the exact prompts it was shown.

## Use of NVIDIA and Nebius

All model calls go through **Nebius Token Factory** (OpenAI-compatible API) using an **NVIDIA Nemotron** model in three roles: the target chatbot, the judge, and the defensive advisor.

## Architecture

- Backend: Python, FastAPI, SQLite (run history), OpenAI SDK pointed at Nebius.
- Frontend: plain HTML, CSS and JavaScript dashboard served by the backend.
- Mock mode runs the full loop with no API key, for demos and automated tests.

## Scope and limits

- Tests run only against our own sample chatbot with fictional secrets.
- A high score describes this test suite only; it is not a security certification.
- Suggestions are advisory and must be reviewed before use.
