# LeadSync — Copilot Agent Instructions
> Read this entirely before writing any code. Hackathon MVP — ruthless scope discipline required.

---

## 0. Before Every Task — Check the Roadmap

**Always read `documentation/ROADMAP.md` before starting any work.**

1. Find the task in the roadmap. If it isn't there, don't build it.
2. Identify which developer owns it: **Dev 1 (API & Integration)** or **Dev 2 (Crew Logic & Content)**. Do not cross the boundary — each developer owns their layer.
3. Check if the task is blocked. If a prior checkpoint hasn't been reached, stop and flag it rather than working around it.
4. After completing a task or reaching a checkpoint, update `documentation/ROADMAP.md` — mark checkboxes done and update the Status Log table at the bottom.

---

## 1. Project Identity

**LeadSync** is an agentic context engine: Jira webhook fires → CrewAI agents enrich the ticket → a paste-ready AI prompt is attached back to Jira → dev copies it into their coding environment.

**Stack:** FastAPI · CrewAI · Composio (Jira, GitHub, Slack only) · Gemini via LiteLLM · Python 3.11+
**Deploy target:** ngrok + Railway

---

## 2. Project Structure

```
leadsync/
├── src/
│   ├── main.py              # FastAPI app + all endpoints
│   ├── shared.py            # Shared: LLM factory, env helpers, Composio client
│   ├── leadsync_crew.py     # Workflow 1: Ticket Enrichment
│   ├── digest_crew.py       # Workflow 2: End-of-Day Digest
│   └── slack_crew.py        # Workflow 3: Slack Q&A
├── templates/
│   ├── backend-ruleset.md
│   ├── frontend-ruleset.md
│   └── db-ruleset.md
├── config/
│   └── tech-lead-context.md
├── documentation/
│   ├── PROJECT_IDEA.md
│   └── ROADMAP.md
├── tests/
├── requirements.txt
└── .env
```

Never create files outside this structure without a strong reason.

---

## 3. Three Workflows — Keep Them Separate

| Workflow | Trigger | Agents | Output |
|----------|---------|--------|--------|
| 1 — Ticket Enrichment | `POST /webhooks/jira` | Context Gatherer → Intent Reasoner → Propagator | `prompt-[ticket-key].md` attached to Jira + enriched description + comment |
| 2 — End-of-Day Digest | `POST /digest/trigger` | GitHub Scanner → Digest Writer → Slack Poster | One Slack message with grouped commit summary |
| 3 — Slack Q&A | `POST /slack/commands` | Context Retriever → Tech Lead Reasoner → Slack Responder | Threaded Slack reply with reasoned answer |

**Never conflate these into one crew. Three separate files, three separate crews.**

Workflow 1 output is **one file only**: `prompt-[ticket-key].md`. It contains Task + Context + Constraints + Implementation Rules + Expected Output in a single paste-ready document.

---

## 4. Implementation Rules

### Agents
- Max 3 agents per crew. No exceptions.
- `verbose=True` on every agent and crew — logs are the demo.
- Only give each agent the tools it needs. Reasoner agents get no tools.
- LLM via env var `LEADSYNC_GEMINI_MODEL`. Default constant: `gemini/gemini-2.5-flash`. Never hardcode beyond the default.

### Composio (locked pattern — do not change)
- All Jira, GitHub, Slack interactions go through Composio. No raw API calls.
- Use `Composio(provider=CrewAIProvider())` + `composio.tools.get(user_id=..., toolkits=[...])`.
- See `src/leadsync_crew.py:_build_tools` for the reference implementation.
- ❌ Do NOT use `ComposioToolSet` or `toolset.get_tools(actions=[...])` — different pattern, not used here.
- `COMPOSIO_USER_ID` from env (default: `"default"`). Only toolkits: `JIRA`, `GITHUB`, `SLACK`.

### Templates & Config
- Load rulesets at runtime from `templates/`. Select by ticket label.
- Load tech lead context at runtime from `config/tech-lead-context.md`.
- Never hardcode template content inline in agent prompts.

### Shared Utilities
- `src/shared.py` exports: `_required_env()`, `build_llm()`, `build_tools()`.
- All crew files import from `shared.py`. Never duplicate these helpers.

### FastAPI
- All endpoints in `src/main.py`. No router splitting.
- Extract payload fields with `.get()` and safe defaults.
- Return `{"status": "processed", "model": ..., "result": ...}` on success.
- Raise `HTTPException(400)` for missing env vars, `HTTPException(500)` for crew failures.

---

## 5. Environment Variables

| Variable | Required | Default |
|----------|----------|---------|
| `GEMINI_API_KEY` | Yes | — |
| `COMPOSIO_API_KEY` | Yes | — |
| `SLACK_CHANNEL_ID` | Yes (WF2+3) | — |
| `COMPOSIO_USER_ID` | No | `"default"` |
| `LEADSYNC_GEMINI_MODEL` | No | `gemini/gemini-2.5-flash` |

`_required_env(name)` in `shared.py` raises `RuntimeError` with a clear message when a required var is absent.

---

## 6. Error Handling

- Wrap every `crew.kickoff()` in try/except. Log before re-raising.
- If model name contains `-latest` and error contains `NOT_FOUND`: retry with `-latest` stripped.
- Never silently swallow errors — readable logs are part of the demo.

---

## 7. Coding Standards

- All logic in `src/`. No root-level scripts.
- `@dataclass` for return types (e.g., `CrewRunResult`). Type hints on all function signatures.
- Every file: module docstring at top naming its workflow and exports.
- Every function: docstring with args, return value, side effects.
- Files under 150 lines. No `print()` — use `verbose=True` and FastAPI logging.
- Never commit secrets. All secrets in `.env`, loaded via `python-dotenv`.
- Agent backstories and task descriptions: ≤3 sentences, bullet points preferred.

---

## 8. Testing

- Write tests before implementation (TDD).
- Tests in `tests/` mirroring `src/` structure.
- Mock Composio and `crew.kickoff()` — no real API calls in tests.
- Target ≥60% line coverage: `pytest --cov=src --cov-report=term-missing -q`
- All tests must pass before any handoff.

---

## 9. What's Cut — Do Not Re-Add

- ❌ Two output files per ticket — one `prompt-[ticket-key].md` only
- ❌ PR webhooks — main branch commits only
- ❌ Any UI or dashboard
- ❌ Persistent database
- ❌ Cron/schedulers — digest is a manual HTTP trigger
- ❌ More than 3 agents per crew
- ❌ One mega-crew for multiple workflows
- ❌ Any toolkit besides `JIRA`, `GITHUB`, `SLACK`

If a feature isn't in `documentation/ROADMAP.md`, it doesn't exist for this hackathon.
