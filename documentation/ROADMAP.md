# LeadSync — Hackathon ROADMAP
> 14-hour sprint. Two developers. Three workflows. This document is the single source of truth for what to build, who owns it, and when it must be done.
> Update task checkboxes as you go. Adjust timelines in the buffer if needed — never skip checkpoints.

---

## Developer Split (Fixed for entire sprint)

### Dev 1 — API & Integration Layer
Everything that touches external services: Composio auth, endpoint wiring, E2E testing, deploy.

### Dev 2 — Crew Logic & Content Layer
Everything that can be built without Composio working: shared utilities, templates, crew files, tests.

> **Rule:** Dev 1 never writes crew logic. Dev 2 never writes FastAPI endpoints. This keeps merge conflicts near zero.

---

## Timeline

```
Hour 0-2   PARALLEL FOUNDATION
Hour 2-5   PARALLEL BUILD
Hour 5     ⛳ CHECKPOINT — Workflow 1 demo-ready
Hour 5-8   PARALLEL INTEGRATION
Hour 8     ⛳ CHECKPOINT — All 3 workflows fire without exceptions
Hour 8-11  POLISH + DEPLOY
Hour 11    ⛳ CHECKPOINT — Live deploy, tests passing
Hour 11-13 DEMO REHEARSAL
Hour 13-14 BUFFER (contingency only)
```

---

## Hour 0–2 — Parallel Foundation

### Dev 1
- [ ] Verify Composio auth: `composio whoami` returns your account
- [ ] Run tool verification script — JIRA + GITHUB tools must return non-empty list
  ```python
  from composio import Composio
  from composio_crewai import CrewAIProvider
  c = Composio(provider=CrewAIProvider())
  tools = c.tools.get(user_id="default", toolkits=["JIRA", "GITHUB"])
  print([t.name for t in tools])  # Must not be empty
  ```
- [ ] Add SLACK toolkit verification once Slack is connected
- [ ] Confirm `.env` has all required keys: `GEMINI_API_KEY`, `COMPOSIO_API_KEY`, `SLACK_CHANNEL_ID`
- [ ] Run `uvicorn src.main:app --reload` — `/health` must return `{"status": "ok"}`

### Dev 2
- [ ] Create `src/shared.py` with three exports:
  - `_required_env(name: str) -> str` — raises `RuntimeError` if missing
  - `build_llm() -> str` — reads `LEADSYNC_GEMINI_MODEL`, defaults to `gemini/gemini-2.5-flash`
  - `build_tools(toolkits: list[str]) -> list` — wraps Option A Composio pattern, reads `COMPOSIO_USER_ID`
- [ ] Create `templates/backend-ruleset.md` (async patterns, API contracts, rate limiting, error handling)
- [ ] Create `templates/frontend-ruleset.md` (component boundaries, state management, accessibility, testing)
- [ ] Create `templates/db-ruleset.md` (migration safety, indexing, query performance, transactions)
- [ ] Create `config/tech-lead-context.md` — architectural preferences, non-negotiables, team notes, per-label rules
- [ ] Refactor `leadsync_crew.py` to import from `shared.py` instead of duplicating helpers

---

## Hour 2–5 — Parallel Build

### Dev 1
- [ ] Fire golden test payload at running server:
  ```bash
  curl -X POST http://localhost:8000/webhooks/jira \
    -H "Content-Type: application/json" \
    -d '{"issue":{"key":"LEADS-1","fields":{"summary":"Add rate limiting","labels":["backend"],"assignee":{"displayName":"Alice"},"project":{"key":"LEADS"},"components":[]}}}'
  ```
- [ ] Watch logs — all 3 agents must fire in sequence with `verbose=True` output
- [ ] Confirm Jira ticket `LEADS-1` is updated: description enriched, comment posted, `prompt-LEADS-1.md` attached
- [ ] Fix any Composio tool call failures — consult Dev 2 if crew logic is wrong, fix endpoint/auth if it's a connection issue
- [ ] Do not move on until Jira shows the attachment

### Dev 2
- [ ] Refactor `leadsync_crew.py` — Reasoner loads correct ruleset template by label:
  ```python
  label = labels[0] if labels else "backend"
  ruleset_map = {"backend": "backend-ruleset.md", "frontend": "frontend-ruleset.md", "database": "db-ruleset.md"}
  ruleset = Path(f"templates/{ruleset_map.get(label, 'backend-ruleset.md')}").read_text()
  ```
- [ ] Reasoner generates a single `prompt-[ticket-key].md` with this structure:
  ```
  ## Task
  ## Context (recent commits + linked tickets)
  ## Constraints
  ## Implementation Rules (from ruleset)
  ## Expected Output
  ```
- [ ] Propagator task: attach the generated file to Jira + update ticket description + post comment
- [ ] Create `src/digest_crew.py` with 3 agents:
  - `GitHubScanner` — scans main branch commits from last 24h (Composio GITHUB tools)
  - `DigestWriter` — groups by area, writes natural-language summary (no tools)
  - `SlackPoster` — posts to `SLACK_CHANNEL_ID` (Composio SLACK tools)
  - Export: `run_digest_crew() -> CrewRunResult`
- [ ] Create `src/slack_crew.py` with 3 agents:
  - `ContextRetriever` — fetches Jira ticket + loads `config/tech-lead-context.md` (Composio JIRA tools)
  - `TechLeadReasoner` — reasons from tech lead perspective, no tools, uses loaded context
  - `SlackResponder` — posts threaded reply (Composio SLACK tools)
  - Export: `run_slack_crew(ticket_key: str, question: str) -> CrewRunResult`

---

## ⛳ Checkpoint H5 — Workflow 1 Demo-Ready

**Both devs stop and verify together:**
- [ ] `curl` golden payload → no exceptions in server logs
- [ ] Refresh Jira `LEADS-1` → description is enriched, comment exists, `prompt-LEADS-1.md` is attached
- [ ] Open `prompt-LEADS-1.md` → has all 5 sections, reads like a real paste-ready agent prompt
- [ ] Try a `frontend` label → correct ruleset loaded (check Reasoner logs)

**Do not proceed to Hour 5–8 until all four are checked.**

---

## Hour 5–8 — Parallel Integration

### Dev 1
- [ ] Add `POST /digest/trigger` endpoint to `src/main.py`:
  - Calls `run_digest_crew()`
  - Returns `{"status": "processed", "model": ..., "result": ...}`
  - Raises `HTTPException(400)` on missing env, `HTTPException(500)` on crew failure
- [ ] Add `POST /slack/commands` endpoint to `src/main.py`:
  - Parses body for `ticket_key` and `question` (or Slack slash command format: `text = "LEADS-1 Should I extend the users table?"`)
  - Calls `run_slack_crew(ticket_key, question)`
  - Returns same response shape
- [ ] Test `/digest/trigger` — fire it, verify Slack message appears in channel
- [ ] Test `/slack/commands` — fire with LEADS-1 payload, verify threaded Slack reply

### Dev 2
- [ ] Write `tests/test_shared.py`:
  - `_required_env` raises `RuntimeError` on missing var
  - `_required_env` returns value when present
  - `build_llm()` returns default model when env var unset
- [ ] Write `tests/test_leadsync_crew.py`:
  - Mock `build_tools()` to return empty list
  - Mock `crew.kickoff()` to return fake result
  - Assert `run_leadsync_crew()` returns `CrewRunResult` with correct shape
  - Assert model fallback logic strips `-latest` and retries
- [ ] Write `tests/test_main.py`:
  - `/health` returns 200
  - `/webhooks/jira` happy path (mock crew, assert 200 + response shape)
  - `/webhooks/jira` missing env var → 400
  - `/webhooks/jira` crew exception → 500
- [ ] Fill out `config/tech-lead-context.md` with real demo content:
  - At minimum: 3 architectural preferences, 2 non-negotiables, 1 team-member note, 1 per-label rule
  - This is what makes Workflow 3 feel like a real tech lead, not a summarizer
- [ ] Run `pytest --cov=src --cov-report=term-missing -q` — fix anything under 60%

---

## ⛳ Checkpoint H8 — All 3 Workflows Fire

**Both devs verify:**
- [ ] `POST /webhooks/jira` → Jira updated (from Checkpoint H5, still works)
- [ ] `POST /digest/trigger` → Slack message in channel
- [ ] `POST /slack/commands` with `{"ticket_key": "LEADS-1", "question": "Should I extend the users table?"}` → Threaded Slack reply with reasoned answer (not a ticket summary)
- [ ] `pytest` passes with ≥60% coverage

**Do not proceed to deploy until all four are checked.**

---

## Hour 8–11 — Polish + Deploy

### Dev 1
- [ ] Set up ngrok: `ngrok http 8000` → copy public URL
- [ ] Register ngrok URL as Jira webhook (`<ngrok-url>/webhooks/jira`)
- [ ] Register `/leadsync` Slack slash command pointing to `<ngrok-url>/slack/commands`
- [ ] Deploy to Railway:
  - Add all env vars from `.env` to Railway dashboard
  - Confirm `/health` returns 200 on Railway URL
  - Update Jira webhook + Slack slash command to Railway URL
- [ ] Verify full Workflow 1 fires from real Jira ticket creation (not just curl)

### Dev 2
- [ ] Error handling pass across all crew files:
  - `-latest` fallback in `digest_crew.py` and `slack_crew.py` (same pattern as `leadsync_crew.py`)
  - All `crew.kickoff()` calls wrapped in try/except with logging
- [ ] Tighten agent prompts — backstories ≤3 sentences, task descriptions use bullet points
- [ ] Verify no `print()` statements exist anywhere in `src/`
- [ ] Check all files are under 150 lines — split if over
- [ ] Run final `pytest` — all tests green

---

## ⛳ Checkpoint H11 — Live Deploy + Tests Green

- [ ] Railway URL is live, `/health` returns 200
- [ ] Real Jira ticket creation fires Workflow 1 (webhook registered, not just curl)
- [ ] `pytest` all green, ≥60% coverage
- [ ] Slack slash command registered and reachable

---

## Hour 11–13 — Demo Rehearsal

Run the full 4-minute demo script twice. Both devs present it at least once.

### Beat 1 — Ticket Enrichment (~90 sec)
1. Create Jira ticket: title `"add rate limiting"`, label `backend`, assign to Alice. No description.
2. Show the sparse ticket to audience.
3. Watch server logs stream live — agents fire in sequence.
4. Refresh Jira — description enriched, comment posted, `prompt-LEADS-1.md` attached.
5. Open the file — complete paste-ready prompt. Say: *"Alice pastes this into Claude Code, zero additional input needed."*

### Beat 2 — End-of-Day Digest (~45 sec)
1. Hit `POST /deploy/trigger` (curl or Railway test).
2. Watch logs — GitHub scanned, commits grouped, Slack message composed.
3. Open Slack — message in channel with grouped digest.
4. Say: *"Every evening, the team sees what shipped. Zero standup prep."*

### Beat 3 — Slack Q&A (~45 sec)
1. In Slack: `/leadsync LEADS-1 Should I extend the users table or create a new one?`
2. Watch logs — ticket fetched, tech lead context loaded, reasoning applied.
3. Reply appears in Slack thread — opinionated answer, not a ticket summary.
4. Say: *"This is the tech lead's judgment, available 24/7, without the ping."*

### Rehearsal Checklist
- [ ] Run 1 complete — time it (target: under 5 min)
- [ ] Run 2 complete — identify anything that looks bad on screen and fix it
- [ ] Logs are readable on screen (font size, terminal layout)
- [ ] Jira and Slack are open in separate tabs, ready to switch

---

## Hour 13–14 — Buffer

Use only if something broke in rehearsal. Priority order if time is short:
1. Fix Workflow 1 (most demo-critical)
2. Fix Workflow 3 Slack reply (high visual impact)
3. Fix Workflow 2 digest (least critical, but still strong)

---

## Integration Contracts

Dev 1 can stub these imports until Dev 2 delivers them:

| Module | Function signature | Due |
|--------|--------------------|-----|
| `src.shared` | `build_llm() -> str` | Hour 1 |
| `src.shared` | `build_tools(toolkits: list[str]) -> list` | Hour 1 |
| `src.shared` | `_required_env(name: str) -> str` | Hour 1 |
| `src.digest_crew` | `run_digest_crew() -> CrewRunResult` | Hour 5 |
| `src.slack_crew` | `run_slack_crew(ticket_key: str, question: str) -> CrewRunResult` | Hour 6 |

---

## What's Cut — Do Not Re-Add

- Two output files per ticket — one `prompt-[ticket-key].md` only
- PR webhooks — main branch commits scanned on-demand only
- Any persistent database
- Cron/schedulers — digest is manual HTTP trigger
- Frontend, dashboard, or any UI
- More than 3 agents per crew
- One mega-crew handling multiple workflows
- Notion, email, or any toolkit besides JIRA, GITHUB, SLACK

---

## Status Log

Update this after each checkpoint.

| Checkpoint | Status | Notes |
|------------|--------|-------|
| H5 — Workflow 1 demo-ready | pending | |
| H8 — All 3 workflows fire | pending | |
| H11 — Live deploy + tests | pending | |
| Demo rehearsal done | pending | |
