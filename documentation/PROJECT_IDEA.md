# LeadSync — PROJECT_IDEA.md
> Coding agent context doc. Read before writing any code. Do not deviate from this scope.

## One-Sentence Value Prop
LeadSync is an agentic context engine that automatically enriches Jira tickets with personalized AI prompts and dev-specific rulesets — so developers never need to ping the tech lead for clarification.

---

## The Problem We're Solving

Tech lead creates a quick Jira ticket → devs ping them 20x/day for context → LeadSync fires automatically on ticket creation/assignment, gathers context from Jira + GitHub, and attaches a copy-paste-ready AI prompt + ruleset directly in the ticket. Devs just open Jira, grab the file, paste into Claude Code.

---

## The One Workflow (Do Not Add Others)

```
TRIGGER: Jira webhook → jira:issue_created OR jira:issue_assigned
         POST /webhooks/jira  [FastAPI]

AGENT A — Context Gatherer
  - Composio/Jira: fetch full issue (summary, description, labels, assignee, linked issues)
  - Composio/GitHub: list_commits(repo, branch=main, since=last 24h)

AGENT B — Intent Reasoner
  - Read ticket labels → select ruleset template:
      "backend"  → load backend-ruleset.md
      "frontend" → load frontend-ruleset.md
      "database" → load db-ruleset.md
  - LLM generates:
      1. Personalized AI prompt (task + context + assignee role + rules + constraints + output format)
      2. Dev-specific ruleset snippet (.claude.md style)

AGENT C — Propagator
  - Composio/Jira: append enriched context to ticket description
  - Composio/Jira: attach  ai-prompt-[assignee].md
  - Composio/Jira: attach  rules-[assignee].md
  - Composio/Jira: add comment "AI prompt + ruleset ready for Claude Code."

STRETCH (only if core is done and stable):
  - Slack /context JIRA-123 → returns context summary from the attached prompt
  - Skyfire token attached to Jira ticket (signed proof prompt is agent-generated)
```

---

## Tech Stack (Locked — No Substitutions)

| Layer | Choice | Notes |
|-------|--------|-------|
| Backend | FastAPI (Python) | Single file ok for MVP |
| Agents | CrewAI — 3 agents, 1 sequential Flow | No more than 3 agents |
| Tool layer | Composio ONLY | No raw API calls — judges are watching |
| LLM | claude-3-5-sonnet-20240620 | Fallback: claude-3-opus |
| Templates | 3 .md files in /templates | Hardcoded, no DB |
| Tunnel | ngrok (local) → Railway (deploy) | |
| Frontend | None | Logs/status page only if 2h+ ahead of schedule |

---

## Project File Structure

```
leadsync/
├── main.py                  # FastAPI app + webhook endpoint
├── agents.py                # CrewAI agents + tasks + crew definition
├── tools.py                 # Composio toolset initialization
├── templates/
│   ├── backend-ruleset.md
│   ├── frontend-ruleset.md
│   └── db-ruleset.md
├── requirements.txt
└── .env                     # ANTHROPIC_API_KEY, COMPOSIO_API_KEY
```

---

## Exact Dependencies

```txt
# requirements.txt
fastapi==0.115.0
uvicorn==0.32.0
crewai==0.60.1
composio-core==0.4.15
composio-crewai==0.4.15
python-dotenv
```

---

## Core Code Skeleton

### main.py
```python
from fastapi import FastAPI, Request
from agents import context_crew

app = FastAPI()

@app.post("/webhooks/jira")
async def jira_webhook(request: Request):
    payload = await request.json()
    issue_key = payload["issue"]["key"]
    result = context_crew.kickoff(inputs={"jira_payload": payload})
    return {"status": "processed", "issue": issue_key}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### agents.py
```python
from crewai import Agent, Task, Crew, Process
from composio_crewai import ComposioToolSet, App

toolset = ComposioToolSet()
jira_tools = toolset.get_tools(apps=[App.JIRA])
github_tools = toolset.get_tools(apps=[App.GITHUB])

context_gatherer = Agent(
    role="Context Gatherer",
    goal="Pull full Jira issue details and recent GitHub commits to main",
    backstory="You extract raw context from Jira and GitHub for downstream agents.",
    tools=[*jira_tools, *github_tools],
    llm="claude-3-5-sonnet-20240620",
    verbose=True,
    max_iter=3
)

intent_reasoner = Agent(
    role="Intent Reasoner",
    goal="Generate a personalized AI prompt and dev ruleset based on ticket labels",
    backstory="You translate technical context into actionable developer instructions.",
    llm="claude-3-5-sonnet-20240620",
    verbose=True,
    max_iter=3
)

propagator = Agent(
    role="Propagator",
    goal="Update Jira ticket with enriched description and attach generated files",
    backstory="You write back to Jira — updating descriptions and attaching prompt/ruleset files.",
    tools=[*jira_tools],
    llm="claude-3-5-sonnet-20240620",
    verbose=True,
    max_iter=3
)

gather_task = Task(
    description=(
        "Pull the full Jira issue for {jira_payload[issue][key]} including summary, "
        "description, labels, assignee, and linked issues. "
        "Also list GitHub commits to main in the last 24h for the relevant repo."
    ),
    agent=context_gatherer,
    expected_output="Dict with issue details + list of recent commits"
)

reason_task = Task(
    description=(
        "Read ticket labels to select the correct ruleset template: "
        "'backend' → backend-ruleset.md, 'frontend' → frontend-ruleset.md, 'database' → db-ruleset.md. "
        "Load the matching template from the /templates/ directory. "
        "Generate: (1) a personalized AI prompt for the assignee, (2) a dev ruleset snippet."
    ),
    agent=intent_reasoner,
    context=[gather_task],
    expected_output="Two markdown strings: ai_prompt and ruleset"
)

propagate_task = Task(
    description=(
        "Update the Jira ticket description with a context summary. "
        "Attach ai-prompt-[assignee].md and rules-[assignee].md as file attachments. "
        "Add comment: 'AI prompt + ruleset ready for Claude Code.'"
    ),
    agent=propagator,
    context=[gather_task, reason_task],
    expected_output="Confirmation that description updated, files attached, and comment posted"
)

context_crew = Crew(
    agents=[context_gatherer, intent_reasoner, propagator],
    tasks=[gather_task, reason_task, propagate_task],
    process=Process.sequential,
    verbose=True
)
```

---

## Composio Setup (Run in This Order)

```bash
pip install composio-core composio-crewai crewai fastapi uvicorn python-dotenv

# Authenticate (browser OAuth)
composio add jira
composio add github
composio add slack  # only if doing stretch goal

# Verify tools work BEFORE writing agent code
composio run jira --action get_issue --args '{"issue_key": "LEADS-1"}'
composio run github --action list_commits --args '{"owner": "yourorg", "repo": "userservice", "sha": "main"}'
```

**Do not proceed past Composio setup until both test commands return real data.**

---

## Ruleset Templates (Hardcode These Exactly)

### templates/backend-ruleset.md
```markdown
# Backend Ruleset

ALWAYS:
- Use async/await for all I/O
- Add OpenAPI spec changes alongside code
- Write load tests (target: 1000 req/min)
- Use dependency injection, not global state

NEVER:
- Blocking I/O in async routes
- Hardcoded secrets or config values
- Skip error handling on external calls

STACK DEFAULTS:
- Rate limiting: Redis + token bucket
- Auth: JWT, validated middleware-side
- Logging: structured JSON
```

### templates/frontend-ruleset.md
```markdown
# Frontend Ruleset

ALWAYS:
- Component-first: one responsibility per component
- Handle loading + error states explicitly
- Write Storybook stories for UI components

NEVER:
- Fetch data in render functions
- Inline styles (use CSS modules or Tailwind)
- Skip accessibility attributes (aria-*)

STACK DEFAULTS:
- State: React Query for server state
- Forms: React Hook Form + Zod validation
- Testing: Vitest + Testing Library
```

### templates/db-ruleset.md
```markdown
# Database Ruleset

ALWAYS:
- Write migrations for every schema change
- Add indexes on foreign keys and query columns
- Use transactions for multi-table writes

NEVER:
- Raw string SQL (use parameterized queries)
- Migrations that delete columns directly (deprecate first)
- Skip EXPLAIN ANALYZE on new queries

STACK DEFAULTS:
- ORM: SQLAlchemy async
- Migrations: Alembic
- Connection pool: asyncpg, max 10 connections
```

---

## Generated AI Prompt Format (Agent B produces this)

```markdown
# AI Prompt for [ASSIGNEE] — [JIRA-KEY]

## Task
[ticket summary]

## Context
Recent commits to main (last 24h):
- [commit message + files changed]
- [commit message + files changed]

Related tickets:
- [linked issue summary if any]

## Your Role
[Assignee]'s context: [inferred from assignee name + label]

## Rules
[Contents of label-matched ruleset template]

## Constraints
- [Inferred from ticket description and commits]
- Do not break existing interface contracts

## Output Format
1. Implementation code
2. Unit tests
3. Updated OpenAPI spec (if applicable)
4. One-line changelog entry
```

---

## Golden Demo Data

| Field | Value |
|-------|-------|
| Jira project | LEADS |
| Ticket | LEADS-1 |
| Summary | Add rate limiting to /api/users |
| Label | `backend` |
| Assignee | Alice |
| GitHub repo | your fork with 3 recent main commits |
| Expected output | 2 attachments + 1 comment in Jira |

**Pre-stage these 3 commits in your GitHub repo main branch before the demo:**
```
feat: add Redis client initialization to user-service
fix: remove in-memory session store
chore: update rate limiter config schema
```

---

## Demo Script (2.5 min)

| Time | Action | What judges see |
|------|--------|-----------------|
| 0:00–0:20 | Narrate the problem | "20 pings/day for context. LeadSync ends this." |
| 0:20–0:40 | Create LEADS-1 in Jira | Label: backend, Assign: Alice |
| 0:40–1:20 | Watch backend terminal | Agent A/B/C logs streaming live |
| 1:20–2:00 | Refresh Jira ticket | 2 attachments + enriched description + comment |
| 2:00–2:30 | Open ai-prompt-alice.md | "Paste into Claude Code. Done." |
| 2:30–3:00 | Close | "Zero UI. Fits existing workflow. One webhook." |

---

## Build Order (12h Engineering Budget)

```
[0–2h]   FastAPI /webhooks/jira + ngrok tunnel + Jira webhook pointing at it
[2–5h]   CrewAI 3 agents + sequential flow + Composio tools wired
[5–7h]   Ruleset templates + Agent B prompt generation verified
[7–9h]   Agent C Jira attachments working end-to-end (test attach_file standalone first)
[9–10h]  Full golden demo: run 10x, fix failures, add mock fallbacks if needed
[10–11h] Slack /context Q&A (stretch — skip if behind)
[11–12h] Skyfire token (stretch) + optional logs status page
[12–24h] Pitch practice + record backup screen capture
```

---

## What's Cut (Do Not Re-Add)

- ❌ Notion updates
- ❌ PR webhooks (main branch commits only, pulled on-demand via Composio)
- ❌ Nightly digest
- ❌ Custom dashboard or UI
- ❌ More than 3 agents
- ❌ Raw requests to Jira/GitHub API (Composio only)
- ❌ Database or persistent storage

---

## Failure Modes to Prevent

| Risk | Prevention |
|------|-----------|
| Composio auth breaks at demo | Pre-auth all apps day before, test tokens explicitly |
| Agent B picks wrong ruleset | Hardcode label→template map in task description, don't rely on LLM to infer |
| Jira attachment API fails | Test `attach_file` Composio action standalone before wiring agents |
| Agent hangs | Set `max_iter=3` on every agent |
| ngrok URL changes | Use ngrok static domain or paid plan |
| Silent failure | `verbose=True` on every Agent and Crew |

---

## Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...
COMPOSIO_API_KEY=...
JIRA_PROJECT_KEY=LEADS
GITHUB_ORG=yourorg
GITHUB_REPO=userservice
```

---

## Coding Agent Rules (Non-Negotiable)

1. **Composio only** — never call `requests.get("https://api.github.com/...")` directly
2. **3 agents max** — gatherer, reasoner, propagator
3. **Sequential process** — `Process.sequential`, not hierarchical or parallel
4. **Templates are files** — load from `/templates/` dir at runtime, not hardcoded strings in prompts
5. **Attachments are the deliverable** — `ai-prompt-[dev].md` and `rules-[dev].md` must appear in Jira as attachments
6. **Demo path is sacred** — every code decision must keep the golden demo (LEADS-1, Alice, backend label) working
7. **Verbose always** — never suppress logs during development or demo