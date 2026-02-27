# LeadSync — Claude Code Agent Instructions
> Read this entirely before writing any code. This is a hackathon MVP. Ruthless scope discipline required.

---

## 1. Project Identity

**LeadSync** is an agentic context engine: Jira webhook fires → CrewAI agents enrich the ticket → personalized AI prompt + ruleset attached back to Jira → dev copies and pastes into Claude Code.

**Stack:** FastAPI · CrewAI · Composio (Jira + GitHub only) · Gemini (via LiteLLM) · Python 3.11+
**Deploy target:** ngrok + Railway (webhook must be reachable externally)
**Time budget:** 12h engineering max. MVP ships or we lose.

---

## 2. Project Structure

```
leadsync/
├── src/
│   ├── main.py                  # FastAPI app + all endpoints
│   ├── leadsync_crew.py         # Workflow 1: Ticket Enrichment crew
│   ├── digest_crew.py           # Workflow 2: End-of-Day Digest crew
│   └── slack_crew.py            # Workflow 3: Slack Q&A crew
├── templates/
│   ├── backend-ruleset.md       # Loaded at runtime by agents
│   ├── frontend-ruleset.md
│   └── db-ruleset.md
├── config/
│   └── tech-lead-context.md     # Tech lead reasoning backbone for Workflow 3
├── documentation/
│   ├── PROJECT_IDEA.md
│   └── ROADMAP.md
├── requirements.txt
└── .env
```

**Rule: Never create files outside this structure without a strong reason.**

---

## 3. Three Workflows — Keep Them Separate

### Workflow 1 — Ticket Enrichment (MUST ship)
**Trigger:** `POST /webhooks/jira`
**Agents:** Context Gatherer → Intent Reasoner → Propagator
**Output:** Two Jira attachments: `ai-prompt-[dev].md` + `rules-[dev].md` + a comment

### Workflow 2 — End-of-Day Digest (SHOULD ship)
**Trigger:** `POST /digest/trigger` (manual HTTP, no cron)
**Agents:** GitHub scanner → Digest writer → Slack poster
**Output:** One Slack message with grouped commit summary

### Workflow 3 — Slack Q&A (COULD ship)
**Trigger:** `POST /slack/commands` (slash command: `/leadsync JIRA-123 [question]`)
**Agents:** Context retriever → Tech Lead Reasoner → Slack responder
**Output:** Threaded Slack reply with opinionated answer (not a summary)

**NEVER conflate these into one crew. Three separate files, three separate crews.**

---

## 4. Non-Negotiable Implementation Rules

### Agents
- **Max 3 agents per crew.** No exceptions.
- `verbose=True` on every agent and crew — logs are part of the demo.
- Each agent gets only the tools it needs. Gatherer + Propagator get Composio tools. Reasoner gets none.
- LLM is configurable via env var `LEADSYNC_GEMINI_MODEL`. Default: `gemini/gemini-2.5-flash`. Never hardcode a model string beyond the default constant.

### Tools
- **Composio only** for all Jira, GitHub, Slack interactions. No raw API calls.
- Auth pattern: `Composio(provider=CrewAIProvider())` + `composio.tools.get(user_id=..., toolkits=[...])`
- Composio user_id comes from env var `COMPOSIO_USER_ID` (default: `"default"`).
- Only these toolkits: `JIRA`, `GITHUB`, `SLACK` — no others.

### Templates & Config
- Ruleset templates live in `templates/`. Load them at runtime with `Path("templates/backend-ruleset.md").read_text()`.
- Tech Lead Context lives in `config/tech-lead-context.md`. Same load pattern.
- Never hardcode template content inline in agent prompts.

### Output Files
- Workflow 1 produces exactly **two files per ticket**: `ai-prompt-[ticket-key].md` and `rules-[ticket-key].md`.
- Files are attached to the Jira ticket via Composio. Do not email, Slack, or store them elsewhere.
- PROJECT_IDEA.md describes a one-file approach — **ignore that**. Demo needs two distinct artifacts for visual impact with judges.

### FastAPI
- All endpoints in `src/main.py`. No router splitting for MVP.
- Webhook validation: extract `issue.key`, `issue.fields.summary`, `issue.fields.labels`, `issue.fields.assignee.displayName` — handle missing keys gracefully with `.get()` and defaults.
- Return `{"status": "processed", "model": ..., "result": ...}` on success.
- Raise `HTTPException(400)` for missing env vars, `HTTPException(500)` for crew failures.
- `load_dotenv()` at app startup.

---

## 5. Environment Variables

```env
GEMINI_API_KEY=           # Required — also set as GOOGLE_API_KEY
COMPOSIO_API_KEY=         # Required
COMPOSIO_USER_ID=default  # Optional, defaults to "default"
LEADSYNC_GEMINI_MODEL=gemini/gemini-2.5-flash  # Optional
SLACK_CHANNEL_ID=         # Required for Workflow 2+3
```

`_required_env(name)` helper must raise `RuntimeError` with a clear message if a required var is missing. FastAPI catches this and returns 400.

---

## 6. Error Handling

- Wrap `crew.kickoff()` in try/except.
- If model name contains `-latest` and error contains `NOT_FOUND`: retry with `-latest` stripped, return result with fallback model name.
- Log all exceptions before re-raising.
- Never silently swallow errors — the demo depends on readable logs.

---

## 7. Composio Setup (Run Once)

```bash
pip install composio-core composio-crewai
composio add jira github slack  # OAuth browser flow
composio whoami  # Verify
```

Test Composio connection before building agents:
```python
from composio import Composio
from composio_crewai import CrewAIProvider
c = Composio(provider=CrewAIProvider())
tools = c.tools.get(user_id="default", toolkits=["JIRA"])
print([t.name for t in tools])  # Must print tool list, not empty
```

**PARK Composio auth issues immediately — do not debug mid-build. Use mock tools if blocked.**

---

## 8. Demo Critical Path (Protect This)

```
1. POST /webhooks/jira  →  payload with LEADS-1, label=backend, assignee=Alice
2. Logs stream: Context Gatherer fires → GitHub commits pulled → Intent Reasoner loads backend ruleset
3. Propagator writes back → two attachments appear in Jira + comment posted
4. Judges see: refresh Jira → attachments → open file → complete paste-ready prompt
```

Golden test payload:
```json
{
  "issue": {
    "key": "LEADS-1",
    "fields": {
      "summary": "Add rate limiting",
      "labels": ["backend"],
      "assignee": {"displayName": "Alice"},
      "project": {"key": "LEADS"},
      "components": []
    }
  }
}
```

Test with: `curl -X POST http://localhost:8000/webhooks/jira -H "Content-Type: application/json" -d @test-payload.json`

---

## 9. Build Order (Enforce This)

```
[ ] 1. FastAPI skeleton + /health + /webhooks/jira stub (15 min)
[ ] 2. Three ruleset template files in templates/ (10 min)
[ ] 3. Composio auth + tool list verification (30 min)
[ ] 4. leadsync_crew.py: 3 agents + sequential crew (90 min)
[ ] 5. End-to-end test: webhook → crew → Jira updated (60 min)
[ ] 6. Polish: error handling, fallback model, verbose logs (30 min)
--- DEMO READY AT THIS POINT ---
[ ] 7. digest_crew.py + POST /digest/trigger (60 min)
[ ] 8. slack_crew.py + POST /slack/commands (60 min)
[ ] 9. ngrok + Railway deploy (30 min)
```

**Never skip to step 7+ without a working step 5.**

---

## 10. What's Cut — Do Not Re-Add

- ❌ Any frontend, dashboard, or custom UI
- ❌ PR webhooks — only scan main branch commits
- ❌ Notion, email, or any tool besides Jira/GitHub/Slack
- ❌ Persistent database — flat files and in-memory only
- ❌ Cron jobs or schedulers — digest is manual HTTP trigger
- ❌ More than 3 agents per crew
- ❌ One mega-crew handling all workflows
- ❌ Hardcoded LLM model strings (beyond the default constant)

If a feature isn't in this document, it doesn't exist for this hackathon.

---

## 11. Coding Standards

- All Python files under `src/`. No logic in root-level scripts.
- Use `@dataclass` for return types (see `CrewRunResult` pattern in `leadsync_crew.py`).
- Type hints on all function signatures.
- Keep individual files under 150 lines. Split if larger.
- No `print()` — use agent `verbose=True` and FastAPI's default logging.
- `.env` for all secrets. Never commit secrets. `python-dotenv` loaded at startup.

---

## 12. Maintenance During Build

- Update this file if a new pattern is established (e.g., new Composio toolkit added).
- Do not create new documentation files — update `documentation/ROADMAP.md` for progress tracking.
- After each completed workflow, note it in ROADMAP.md with a one-line status.