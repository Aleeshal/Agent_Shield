# AgentShield: setup and deployment guide

This guide takes you from a fresh clone to a working local app and then to a public deployment.

## What you need to provide

AgentShield needs **one secret**. Everything else has a working default.

| Where | Setting | Status | What to put there |
|---|---|---|---|
| `.env` (local) or host env vars (deployed) | `NEBIUS_API_KEY` | **REQUIRED** | Your API key from the Nebius Token Factory console |
| same | `NEBIUS_MOCK` | **SET** | `0` for real model calls. `1` is demo mode with fake replies and no key needed. |
| same | `NEBIUS_BASE_URL` | CHECK | Default `https://api.tokenfactory.nebius.com/v1/`. Confirm it against the Token Factory docs. |
| same | `NEBIUS_MODEL` | CHECK | Default `nvidia/nemotron-3-super-120b-a12b`. Confirm the exact model ID in the Token Factory model list and that it is an eligible NVIDIA model under the hackathon rules. |
| same | `NEBIUS_DISABLE_THINKING` | only if needed | Set to `1` if real replies come back empty |
| same | `AGENTSHIELD_CONCURRENCY` | only if needed | Lower to `1` or `2` if you get rate-limit errors (HTTP 429) |
| `LICENSE` | license type | CHECK | Currently MIT. Change it if the hackathon rules require a different license. |

In `.env.example`, these lines are marked `>>> REQUIRED` and `>>> CHECK`. No code changes are needed: all settings are read from the environment by `backend/config.py`.

> Never commit `.env` and never paste your key into code or chat. `.env` is already in `.gitignore`.

---

## Part 1: run locally (Windows, PowerShell)

Run these commands from the `Agent_Shield` folder.

### 1. Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activate script, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 2. Create `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

- **Real testing:** paste your key after `NEBIUS_API_KEY=` and keep `NEBIUS_MOCK=0`.
- **Demo without a key:** set `NEBIUS_MOCK=1`.

### 3. Check the model connection (real mode only)

```powershell
python -m scripts.smoke_test
```

Expected: `[1] Model reachable (...)`, followed by one evaluated test. If it fails:

| Message | Fix |
|---|---|
| `NEBIUS_API_KEY is not set` | The key is missing from `.env`, or you are not in the `Agent_Shield` folder |
| `AuthenticationError ... 401` | Wrong or expired key |
| `NotFoundError ... 404` / model not found | `NEBIUS_MODEL` is not an exact model ID from Token Factory |
| `Model returned an empty reply` | Set `NEBIUS_DISABLE_THINKING=1` |
| `RateLimitError ... 429` | Lower `AGENTSHIELD_CONCURRENCY` |
| `APIConnectionError` / timeout | Check `NEBIUS_BASE_URL` and your internet connection; raise `NEBIUS_TIMEOUT` |

Then run the whole suite in the console:

```powershell
python -m scripts.smoke_test --all
```

### 4. Start the app

```powershell
uvicorn backend.main:app --reload
```

- App: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

The chip in the top-right corner shows the mode:
- green: **Nebius · model name** means real calls are working.
- orange: **Mock mode** means `NEBIUS_MOCK=1`.
- red: **NEBIUS_API_KEY not set** means real mode is on but there is no key.

Restart `uvicorn` after editing `.env`. `--reload` only watches code files.

### 5. Run the automated tests (optional)

```powershell
python -m unittest discover -s tests -t . -v
```

The tests always use mock mode and a temporary database. They need no key and do not touch your run history.

---

## Part 2: the demo flow

1. **Run tests**: 24 attacks run against the NovaBank sample chatbot. The default instructions are deliberately weak, so there will be failures.
2. Click any result row to see the attack, the chatbot's reply, and why it passed or failed.
3. **Generate suggestions**: the model proposes fixes and a revised system prompt. You can edit the prompt.
4. **Apply fix & retest**: the same suite runs again, and **Before vs after** shows the score change, fixed and regressed tests, and the holdout result (tests the fixer never saw).
5. Optional: use **Try a custom attack** for live prompts, and **Run history** to compare any two runs.
6. Use **Reset to default** to restore the weak instructions before the next demo.

Timing with a real model: each test makes two model calls (chatbot and judge), so a full run of 24 tests takes about 1 to 3 minutes at concurrency 4, depending on the model's speed. Do one run before presenting to warm up and confirm the setup.

---

## Part 3: deploy

The app is one Python web service: FastAPI serves both the API and the frontend. No database server is needed (it uses SQLite).

### Option A: Render (simplest, free tier available)

1. Push the repository to GitHub.
2. On https://render.com, choose **New → Web Service** and connect the repo.
3. Render detects the `Dockerfile`. Choose **Docker** as the runtime. If the app is in a subfolder of the repo, set **Root Directory** to `Agent_Shield`.
4. Under **Environment**, add:
   - `NEBIUS_API_KEY` = your key **(REQUIRED, add it as a secret)**
   - `NEBIUS_MOCK` = `0`
   - optional: `NEBIUS_MODEL`, `NEBIUS_BASE_URL`, `NEBIUS_DISABLE_THINKING`, `AGENTSHIELD_CONCURRENCY`
5. Deploy. Render sets `$PORT` automatically, and the Dockerfile already listens on it.
6. Open the `https://<your-app>.onrender.com` URL and do one full run to confirm the setup.

Without a disk, run history resets when the service restarts or redeploys. That is fine for a demo. To keep history, add a **Disk** mounted at `/app/data`. The Dockerfile already sets `AGENTSHIELD_DB=/app/data/agentshield.db`.

### Option B: Railway / Fly.io / any Docker host

Use the same `Dockerfile` and the same environment variables. For example:

```bash
docker build -t agentshield .
docker run -p 8000:8000 -e NEBIUS_API_KEY=YOUR_KEY -e NEBIUS_MOCK=0 \
  -v agentshield-data:/app/data agentshield
```

### Option C: a plain VM without Docker

```bash
pip install -r requirements.txt
export NEBIUS_API_KEY=YOUR_KEY NEBIUS_MOCK=0
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Run **one** worker process only (the default). Runs execute in background threads inside the server process, and multiple workers would not share live run state.

### After deploying, check

- [ ] `https://<your-app>/api/health` shows `"mock": false` and `"api_key_set": true`
- [ ] The status chip is green and shows the model name
- [ ] A full run finishes without `inconclusive` results caused by call failures
- [ ] Generate suggestions → Apply fix & retest shows the before/after comparison
- [ ] Instructions are reset to default before judges try it

---

## Security notes

- The API key lives only in `.env` (local) or in the host's secret settings (deployed). It is never sent to the browser.
- Protected values are fictional, and the frontend only receives their labels.
- The deployed app has no login, so anyone with the URL can start runs that use your Nebius credits. Share the URL only with judges, and rotate the key after the hackathon.
