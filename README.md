# LeadSync

**Your tech lead's judgment, available 24/7 — without the ping.**

LeadSync is an agentic context engine that bridges the gap between tech leads and developers. It turns sparse Jira tickets into paste-ready AI prompts, auto-documents pull requests, posts daily digests to Slack, and answers developer questions with the tech lead's actual opinions — not generic summaries.

---

## The Problem

In fast-paced startup teams, developers waste cycles on incomplete tickets, context-switching to ask "how should I build this?", and writing PR descriptions nobody reads. Tech leads repeat themselves. Standups are manual. Onboarding new developers to team conventions is slow.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          TECH LEAD SETUP                                │
│                                                                         │
│  Google Docs (per category)          Jira Label Rulesets                 │
│  ┌──────────┐ ┌──────────┐          ┌──────────────────┐               │
│  │ Backend  │ │ Frontend │ ...      │ templates/       │               │
│  │ Prefs    │ │ Prefs    │          │  backend-ruleset │               │
│  └────┬─────┘ └────┬─────┘          │  frontend-ruleset│               │
│       │             │                │  db-ruleset      │               │
│       └──────┬──────┘                └────────┬─────────┘               │
│              │                                │                         │
└──────────────┼────────────────────────────────┼─────────────────────────┘
               │    Live preferences            │  Rules by ticket label
               ▼                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           LEADSYNC ENGINE                               │
│                                                                         │
│  FastAPI ──► CrewAI Agents ──► Composio ──► External Services           │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │  WF1: Ticket     │  │  WF2: Digest    │  │  WF3: Slack Q&A        │ │
│  │  Enrichment      │  │                 │  │                         │ │
│  │                  │  │  Scans GitHub    │  │  /leadsync TICKET-123  │ │
│  │  Jira webhook    │  │  commits, posts │  │  "Should I use X?"     │ │
│  │  ──► 3 agents    │  │  summary to     │  │  ──► 3 agents reason   │ │
│  │  ──► prompt.md   │  │  Slack          │  │  with tech lead's POV  │ │
│  │  ──► attach Jira │  │                 │  │  ──► Slack reply       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘ │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  WF4: PR Auto-Description                                      │    │
│  │                                                                 │    │
│  │  GitHub webhook ──► analyze diffs ──► enrich PR description     │    │
│  │  (summary + implementation details + validation steps)          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌──────────────┐                                                       │
│  │ SQLite Memory │ ◄── events, Q&A history, leader rules               │
│  └──────────────┘     (contextual retrieval across runs)                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
               │                    │                    │
               ▼                    ▼                    ▼
         ┌──────────┐        ┌──────────┐         ┌──────────┐
         │   Jira   │        │  GitHub  │         │  Slack   │
         │          │        │          │         │          │
         │ enriched │        │ PR desc  │         │ digest + │
         │ ticket + │        │ updated  │         │ Q&A      │
         │ prompt   │        │          │         │ replies  │
         └──────────┘        └──────────┘         └──────────┘
```

---

## Four Workflows

### 1. Ticket Enrichment — Jira Webhook

A developer creates a barebones Jira ticket — just a title, a label (`backend`, `frontend`, or `database`), and an assignee. LeadSync does the rest:

- **Loads the matching ruleset** from `templates/` based on the ticket's Jira label — each category has its own coding rules (e.g., "keep endpoints idempotent", "prefer additive migrations")
- **Pulls the tech lead's live preferences** from Google Docs for that category — architectural decisions, non-negotiables, per-label rules
- **Scans recent GitHub commits** for relevant context and identifies key files
- **Retrieves precedent** from the last 10 completed tickets with the same label
- **Generates a single `prompt-[TICKET-KEY].md`** — a self-contained AI prompt with Task, Context, Key Files, Constraints, Implementation Rules, and Expected Output
- **Attaches it to the Jira ticket**, enriches the description, and posts a comment with same-label history

The developer copies the prompt into Cursor, Claude Code, or any coding agent and starts building — zero additional context needed.

### 2. End-of-Day Digest — Slack

On trigger (manual HTTP call or Railway Cron schedule), agents scan the GitHub repo for recent commits, group them by area of the codebase, and post a structured summary to Slack — what shipped, what's in progress, and patterns worth attention. If nothing shipped, a heartbeat message is posted so the channel stays active. Zero manual standup prep.

### 3. Slack Q&A — Any Team Member

Any developer types `/leadsync TICKET-123 Should I use a new table or extend users?` in Slack. LeadSync classifies the question and responds differently:

| Question Type | Behavior |
|---------------|----------|
| **Implementation** ("Should I...", "Which approach...") | Applies the tech lead's Google Docs preferences for that ticket's category, gives an opinionated recommendation with tradeoffs |
| **Progress** ("What's been done...") | Summarizes completed work from same-label tickets, cites ticket keys |
| **General** ("What is this ticket about?") | Returns factual ticket info without injecting opinions |

The answer feels like the tech lead's judgment — not a ticket summary.

### 4. PR Auto-Description — GitHub Webhook

When a pull request is opened, reopened, or updated against `main`, LeadSync auto-generates a rich PR description:

- **Summary** — AI-generated or cleaned from PR title
- **Context** — detected Jira ticket key + primary code areas touched
- **Implementation Details** — routes, functions, tests, query patterns extracted from diffs
- **Files Changed** — grouped by area (backend / frontend / database / testing)
- **Suggested Validation** — testing steps based on what was touched

The enrichment block is idempotent (HTML comment markers) — re-pushing updates it in place, and any manually written description is preserved.

A sample FastAPI project lives in `demo/fastapi_backend/` specifically for demonstrating this workflow — create a feature branch, make changes there, open a PR to `main`, and watch the description populate itself.

---

## Tech Lead Configuration

LeadSync is powered by two layers of configuration that the tech lead sets up once:

### Category Rulesets (`templates/`)

Three markdown files matched by Jira ticket label:

| Label | Ruleset | Example Rules |
|-------|---------|---------------|
| `backend` | `backend-ruleset.md` | Idempotent endpoints, input validation, success/failure test paths |
| `frontend` | `frontend-ruleset.md` | Accessible UI states, component reuse, critical user flow tests |
| `database` | `db-ruleset.md` | Additive migrations, indexed queries, rollback validation |

### Live Preferences (Google Docs)

The tech lead maintains three Google Docs — one per category — with architectural preferences, non-negotiables, and team-specific rules. These are fetched live on every run (no restart needed). Examples:

- *"Async everywhere — synchronous I/O calls are blocking bugs"*
- *"< 3 new columns tightly coupled -> extend table; new entity -> new table"*
- *"Every endpoint needs rate limit annotation"*

Both rulesets and preferences are automatically injected into Workflow 1 (prompt generation) and Workflow 3 (Slack Q&A reasoning).

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API | **FastAPI** | Webhook endpoints, async request handling |
| AI Agents | **CrewAI** | Multi-agent sequential workflows (max 3 agents per crew) |
| LLM | **Gemini 2.5 Flash** via LiteLLM | Reasoning, summarization, prompt generation |
| Integrations | **Composio** | Unified SDK for Jira, GitHub, Slack, Google Docs |
| Memory | **SQLite** | Event log, Q&A history, leader rules, digest tracking |
| Deploy | **Railway** + **ngrok** | Production hosting + local webhook tunneling |
| Language | **Python 3.11+** | |

---

## Quick Start

```bash
# Clone and setup
git clone <repo-url> && cd leadsync
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Configure .env (see .env.example)
# Required: GEMINI_API_KEY, COMPOSIO_API_KEY, SLACK_CHANNEL_ID

# Run
uvicorn src.main:app --reload
```

Expose locally with ngrok for webhooks:
```bash
ngrok http 8000
```

Point Jira webhook to `<ngrok-url>/webhooks/jira` and GitHub webhook to `<ngrok-url>/webhooks/github`.

---

## API Endpoints

| Endpoint | Method | Trigger |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/webhooks/jira` | POST | Jira webhook (ticket created/assigned) |
| `/webhooks/github` | POST | GitHub webhook (PR opened/updated/synced) |
| `/digest/trigger` | POST | Manual or scheduled digest |
| `/slack/commands` | POST | `/leadsync TICKET-KEY question` |

---

## Project Structure

```
leadsync/
├── src/
│   ├── main.py                 # FastAPI app + all endpoints
│   ├── shared.py               # LLM factory, env helpers, Composio client
│   ├── prefs.py                # Google Docs preference loading
│   ├── workflow1/              # Ticket Enrichment (3 agents)
│   ├── workflow2/              # End-of-Day Digest (3 agents)
│   ├── workflow3/              # Slack Q&A (3 agents)
│   ├── workflow4/              # PR Auto-Description (1 agent + rules)
│   ├── common/                 # Model retry, tool helpers, text extraction
│   └── memory/                 # SQLite schema, read/write/query
├── demo/
│   └── fastapi_backend/        # Sample project for PR auto-description demo
├── templates/                  # Category rulesets (backend, frontend, db)
├── config/                     # Tech lead context defaults
├── tests/                      # 111 tests, 92% coverage
└── documentation/
```

---

## Demo (5 min)

| Beat | Duration | What Happens |
|------|----------|-------------|
| Ticket Enrichment | 90s | Create sparse Jira ticket with label `backend` → agents fire → refresh Jira → paste-ready `prompt-LEADS-1.md` attached |
| PR Auto-Description | 45s | Push changes to `demo/fastapi_backend/` on a feature branch → open PR to `main` → description auto-populated with summary, implementation details, and validation steps |
| Digest | 45s | Hit `/digest/trigger` → Slack message appears with grouped commit summary |
| Slack Q&A | 45s | `/leadsync LEADS-1 Should I extend the users table?` → opinionated answer citing the tech lead's schema rules |

---

## Team

Built at the SVAI Hackathon 2025.
