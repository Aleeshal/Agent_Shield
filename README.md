\# AgentShield



\*\*Test an AI chatbot. Find its weaknesses. Fix them. Prove the fix worked.\*\*



AgentShield is a web app that tests a \*\*sample chatbot\*\* for prompt injection and jailbreak weaknesses. It sends a fixed set of attack messages, checks whether the chatbot broke its rules, explains each failure, suggests a defensive fix, and then \*\*reruns the same tests\*\* to show whether the fix helped.



\- Built for the \*\*Nebius x NVIDIA Global AI Hackathon\*\* by a team of 2 in 7 days.

\- Core loop: \*\*test, detect, fix, retest.\*\*

\- This is a developer testing tool, \*\*not\*\* a certified security assessment. A score only describes performance on our test suite.



> Status: early development. Items marked \*\*\[VERIFY]\*\* in `docs/PROJECT\_PLAN.md` must be checked against the official hackathon rules before relying on them.



\---



\## Quick terms



| Term | Meaning |

|---|---|

| Prompt injection | A user message that tries to make a chatbot ignore its instructions |

| Jailbreak | A message designed to push a chatbot into breaking its safety rules |

| Deterministic check | A plain code rule, for example "does the reply contain the secret string?" |

| Model judge | An AI model that decides whether a reply followed the rules, for cases code cannot decide |

| Inference | Sending a request to a hosted AI model and getting an answer |



\---



\## Project structure and what each file is for



```

Agent\_shield/

|-- README.md

|-- LICENSE

|-- .gitignore

|-- .env.example

|-- requirements.txt

|-- backend/

|   |-- \_\_init\_\_.py

|   |-- main.py

|   |-- config.py

|   |-- nebius\_client.py

|   |-- target\_chatbot.py

|   |-- runner.py

|   |-- evaluator.py

|   |-- suggestions.py

|   |-- scoring.py

|   |-- db.py

|   +-- data/

|       |-- test\_cases.json

|       +-- chatbot\_rules.json

|-- frontend/

|   |-- index.html

|   |-- style.css

|   +-- app.js

|-- docs/

|   |-- PROJECT\_PLAN.md

|   |-- api\_contract.md

|   +-- proposal.md

+-- tests/

&#x20;   +-- .gitkeep

```



\### Root files



| File | What it is and what goes inside |

|---|---|

| `README.md` | This file: overview, structure, setup and run steps. |

| `LICENSE` | The open-source license text. Choose the type after checking the hackathon rules. |

| `.gitignore` | List of files Git must never upload: `.env`, `\_\_pycache\_\_/`, `\*.db`, `.venv/`. |

| `.env.example` | A template listing the setting names (no real values). Copy it to `.env` and fill in your own key. |

| `requirements.txt` | The Python packages to install. Start with `fastapi`, `uvicorn`, `python-dotenv`, `httpx`. |



\### `backend/` (Python, FastAPI)



| File | What it does |

|---|---|

| `\_\_init\_\_.py` | An empty file that lets Python treat `backend` as a package. Needed to run `uvicorn backend.main:app`. |

| `main.py` | The FastAPI app. Defines the API routes and serves the `frontend/` folder. |

| `config.py` | Reads settings (API key, base URL, model name) from the `.env` file. |

| `nebius\_client.py` | One function that sends a prompt to the model on Nebius Token Factory and returns the reply. Every other file calls this instead of talking to the API directly. |

| `target\_chatbot.py` | The sample chatbot being tested: its instructions (system prompt), its rules and its fictional secret. Its instructions must be editable, because that is the "apply fix" step. |

| `runner.py` | Loads the test cases, sends each attack to the target chatbot, collects the replies and passes them to the evaluator. |

| `evaluator.py` | Judges each reply. Step 1: code checks (for example, secret string found). Step 2: model judge returning strict JSON. Invalid output becomes `inconclusive`. |

| `suggestions.py` | Asks the model for advisory defensive suggestions for failed tests. |

| `scoring.py` | Calculates the pass rate and builds the before/after comparison. |

| `db.py` | Saves and loads test runs in SQLite so runs can be compared. |

| `data/test\_cases.json` | The fixed attack suite (about 20 to 30 tests): id, category, prompt, expected safe behavior. |

| `data/chatbot\_rules.json` | The sample chatbot's rules and the fictional protected values. |



\### `frontend/` (plain HTML, CSS, JavaScript)



| File | What it does |

|---|---|

| `index.html` | The page: chatbot rules view, "Run tests" button, results dashboard, suggestions, before/after comparison. |

| `style.css` | The styling. |

| `app.js` | Calls the backend API and fills the page with results. |



\### `docs/` and `tests/`



| File | What it is |

|---|---|

| `docs/PROJECT\_PLAN.md` | Requirements, work split between two people, day-by-day tasks, and what to verify. |

| `docs/api\_contract.md` | The agreed list of API endpoints and the JSON shape of a test result. Both teammates write this together on Day 1. |

| `docs/proposal.md` | The hackathon project proposal. |

| `tests/` | Integration checks that the whole flow works. Kept in Git with a `.gitkeep` placeholder until real files exist. |



\---



\## Setup (Windows)



Use \*\*PowerShell\*\* from the project folder.



\*\*1. Create the `\_\_init\_\_.py` file\*\* (if it does not exist yet):



```powershell

New-Item -ItemType File -Force backend\\\_\_init\_\_.py

```



\*\*2. Create a virtual environment and install packages:\*\*



```powershell

python -m venv .venv

.\\.venv\\Scripts\\Activate.ps1

pip install -r requirements.txt

```



If PowerShell blocks the activate script, run this once and try again:



```powershell

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

```



\*\*3. Add your settings:\*\*



```powershell

Copy-Item .env.example .env

```



Open `.env` and fill in the values from the official Nebius Token Factory documentation:



```

NEBIUS\_API\_KEY=

NEBIUS\_BASE\_URL=

NEBIUS\_MODEL=

```



Never share `.env`, never paste your key in chat or code.



\*\*4. Run the app:\*\*



```powershell

uvicorn backend.main:app --reload

```



\- App: http://127.0.0.1:8000

\- Automatic API docs: http://127.0.0.1:8000/docs



\---



\## How we work together



\- \*\*Member 1 (AI and Backend)\*\* owns everything in `backend/`, plus `.gitignore`, `.env.example` and `requirements.txt`.

\- \*\*Member 2 (Frontend and Product)\*\* owns everything in `frontend/`, plus `README.md`, `LICENSE`, `docs/proposal.md` and `tests/`.

\- Only the owner edits a file. Ask the other person for changes in their files.

\- Both agree `docs/api\_contract.md` on Day 1 so the frontend and backend can be built in parallel.

\- Each person works on their own Git branch, runs `git pull origin main` before starting, and merges small changes daily.

\- Short daily sync: what is done, what is blocked, what is cut.



Full details are in `docs/PROJECT\_PLAN.md`.



\---



\## What counts as done (MVP)



\- A sample chatbot with explicit rules and fictional protected data

\- A fixed suite of about 20 to 30 non-destructive attack tests

\- Real runtime model calls through Nebius Token Factory using an eligible NVIDIA model

\- Code checks plus model-assisted evaluation, with outcomes: pass, confirmed fail, suspected fail, inconclusive

\- A dashboard with results and explanations

\- Advisory defensive suggestions

\- Before-and-after retesting with a comparison

\- A deployed app and a reproducible demo



\## Limits



\- Tests run only against our own sample chatbot with fictional secrets. All attacks are controlled and non-destructive.

\- A high score does not mean a chatbot is secure. It only reflects this test suite.

\- AI suggestions are advisory, not guaranteed fixes.

