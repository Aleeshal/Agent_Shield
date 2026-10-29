# AgentShield

**Test an AI chatbot. Find its weaknesses. Fix them. Prove the fix worked.**

AgentShield is a web app that tests a **sample chatbot** for prompt injection and jailbreak weaknesses. It sends a fixed set of attack messages, checks whether the chatbot broke its rules, explains each failure, suggests a defensive fix, and then **reruns the same tests** to show whether the fix helped.

\*\*Test an AI chatbot. Find its weaknesses. Fix them. Prove the fix worked.\*\*



AgentShield is a web app that tests a \*\*sample chatbot\*\* for prompt injection and jailbreak weaknesses. It sends a fixed set of attack messages, checks whether the chatbot broke its rules, explains each failure, suggests a defensive fix, and then \*\*reruns the same tests\*\* to show whether the fix helped.



\- Built for the \*\*Nebius x NVIDIA Global AI Hackathon\*\* by a team of 2 .

\- Core loop: \*\*test, detect, fix, retest.\*\*

\- This is a developer testing tool, \*\*not\*\* a certified security assessment. A score only describes performance on our test suite.



> Status: early development. Items marked \*\*\[VERIFY]\*\* in `docs/PROJECT\_PLAN.md` must be checked against the official hackathon rules before relying on them.



\---



\## Quick terms

---

## Quick terms

| Term | Meaning |
|---|---|
| Prompt injection | A user message that tries to make a chatbot ignore its instructions |
| Jailbreak | A message designed to push a chatbot into breaking its safety rules |
| Deterministic check | A plain code rule, for example "does the reply contain the secret string?" |
| Model judge | An AI model that decides whether a reply followed the rules, for cases code cannot decide |
| Holdout test | A test hidden from the suggestion step, used to check that a fix generalises |

---

## How it works

1. **Test**: 24 controlled attacks in 11 categories are sent to the NovaBank sample chatbot (`backend/data/test_cases.json`).
2. **Detect**: each reply is judged in two steps:
   - Code checks find protected values in any form (exact, spaced out, reversed, base64) or quoted system instructions → **confirmed fail**.
   - Otherwise a model judge returns strict JSON → **suspected fail** or **pass**. Invalid judge output or a failed call → **inconclusive**.
3. **Fix**: the model reads the failed (non-holdout) tests and proposes advice plus a revised system prompt. You can edit it before applying. If the model fails, rule-based suggestions are used.
4. **Retest**: the same suite runs with the new instructions. The dashboard shows before vs after per test (fixed, regressed, still failing) and the holdout score.

---

## How AgentShield uses NVIDIA and Nebius

- **Nebius Token Factory:** all model inference goes through `backend/nebius_client.py`, a single gateway to Token Factory. It powers three components: the target chatbot (`target_chatbot.py`), the AI judge in `evaluator.py`, and the defensive suggestions in `suggestions.py`.
- **NVIDIA open-source model:** [MODEL NAME, e.g. a Nemotron variant] is set through the `NEBIUS_MODEL` variable in `.env`.
- **Status:** the integration is implemented, but live end-to-end runs were blocked because Token Factory access was unavailable in our region before the deadline.
- ----

## Setup (Windows, PowerShell)

> **Full step-by-step guide, troubleshooting and deployment: [docs/SETUP_AND_DEPLOYMENT.md](docs/SETUP_AND_DEPLOYMENT.md).**
> The only thing you must provide is `NEBIUS_API_KEY`, marked `>>> REQUIRED` in `.env.example`.

From the `Agent_Shield` folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

Open `.env` and set `NEBIUS_API_KEY` (from Nebius Token Factory). `NEBIUS_BASE_URL` and `NEBIUS_MODEL` already have defaults. Never commit `.env`.

**No key yet?** Set `NEBIUS_MOCK=1` in `.env`. The full loop then runs with deterministic fake replies. This is useful for UI work and demos, but it is not a real model evaluation.

## Run

```powershell
uvicorn backend.main:app --reload
```

- App: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

### Demo flow

1. Press **Run tests**. The baseline run shows leaks and rule violations.
2. Click any row to see the attack prompt, the chatbot's reply, and why it failed.
3. Press **Generate suggestions**, review the proposed instructions, then **Apply fix & retest**.
4. The **Before vs after** panel shows the score change, which tests were fixed or regressed, and how the holdout tests did.
5. Use **Try a custom attack** to send your own prompt, and **Run history** to compare any two runs.

### Check the setup

```powershell
python -m scripts.smoke_test          # can we reach the model? runs the first test
python -m scripts.smoke_test --all    # every test, printed to the console
python -m unittest discover -s tests -t . -v   # integration tests (always mock mode, no key needed)
```

If real-model replies come back empty, the model may be using its whole token budget on reasoning. Set `NEBIUS_DISABLE_THINKING=1`. If you hit rate limits, lower `AGENTSHIELD_CONCURRENCY`.

## Deploy

A `Dockerfile` is included. It listens on `$PORT` (default 8000):

```bash
docker build -t agentshield .
docker run -p 8000:8000 -e NEBIUS_API_KEY=... agentshield
```

On Render, Railway or a similar host, deploy the repo as a Docker service and set `NEBIUS_API_KEY` as a secret environment variable. The SQLite run history is stored at `AGENTSHIELD_DB`. Mount a volume there if runs should survive redeploys.

---

## Project structure

```
Agent_Shield/
|-- README.md, LICENSE, requirements.txt, .env.example, Dockerfile
|-- backend/
|   |-- main.py            FastAPI routes; serves the frontend
|   |-- config.py          settings from .env
|   |-- nebius_client.py   the only code that calls Nebius (plus mock mode)
|   |-- target_chatbot.py  the sample chatbot; editable, persisted instructions
|   |-- runner.py          runs the suite in parallel in the background
|   |-- evaluator.py       code checks + model judge -> outcome
|   |-- suggestions.py     defensive advice + revised prompt (with fallback)
|   |-- scoring.py         pass rate, categories, before/after comparison
|   |-- db.py              SQLite run history
|   +-- data/
|       |-- test_cases.json     the attack suite (24 tests, 4 holdout)
|       +-- chatbot_rules.json  rules and fictional protected values
|-- frontend/              index.html, style.css, app.js (no build step)
|-- scripts/smoke_test.py  console proof of concept
|-- tests/test_flow.py     end-to-end integration tests
+-- docs/
    |-- api_contract.md    endpoints and JSON shapes
    +-- proposal.md        hackathon proposal
```

## Team

- **Member 1 (AI and Backend)**: `backend/`, configuration files.
- **Member 2 (Frontend and Product)**: `frontend/`, docs, tests.

## Limits

- Tests run only against our own sample chatbot with fictional secrets. All attacks are controlled and non-destructive.
- A high score does not mean a chatbot is secure. It only reflects this test suite.
- AI suggestions are advisory, not guaranteed fixes.
- The model judge can be wrong. That is why judge-only failures are labelled *suspected*, and code-detected leaks are labelled *confirmed*.
