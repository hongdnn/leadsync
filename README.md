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
│  Google Docs (per category)                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                                │
│  │ Backend  │ │ Frontend │ │ Database │                                 │
│  │ Rules &  │ │ Rules &  │ │ Rules &  │                                 │
│  │ Prefs    │ │ Prefs    │ │ Prefs    │                                 │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘                                │
│       │             │            │                                      │
│       └──────┬──────┘────────────┘                                      │
│              │                                                          │
└──────────────┼──────────────────────────────────────────────────────────┘
               │    Live rules & preferences (matched by Jira label)
               ▼
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
│  ┌──────────────────────────────────┐  ┌──────────────────────────────┐  │
│  │  WF4: PR Auto-Description        │  │  WF5: Jira PR Auto-Link      │  │
│  │                                  │  │                              │  │
│  │  GitHub webhook ──► analyze      │  │  GitHub webhook (PR opened)  │  │
│  │  diffs ──► enrich PR description │  │  ──► extract Jira key        │  │
│  │  (summary + impl + validation)   │  │  ──► post PR link to Jira    │  │
│  │                                  │  │  ──► transition → In Review  │  │
│  └──────────────────────────────────┘  └──────────────────────────────┘  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  WF6: Done Ticket Implementation Scan                           │    │
│  │                                                                 │    │
│  │  Jira webhook (ticket → Done) ──► scan GitHub commits + PRs    │    │
│  │  ──► summarize implementation ──► post summary to Jira          │    │
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

## Six Workflows

### 1. Ticket Enrichment — Jira Webhook

A developer creates a barebones Jira ticket — just a title, a label (`backend`, `frontend`, or `database`), and an assignee. LeadSync does the rest:

- **Loads the team's rules and preferences** from Google Docs for the matching category (backend, frontend, or database) — coding rules, architectural decisions, non-negotiables, all fetched live on every run
- **Scans recent GitHub commits** for relevant context and identifies key files
- **Retrieves precedent** from the last 10 completed tickets with the same label
- **Generates a single `prompt-[TICKET-KEY].md`** — a self-contained AI prompt with Task, Context, Key Files, Constraints, Implementation Rules, and Expected Output
- **Attaches it to the Jira ticket**, enriches the description, and posts a comment with same-label history

The developer copies the prompt into Cursor, Claude Code, or any coding agent and starts building — zero additional context needed.

### 2. End-of-Day Digest — Slack

On trigger (manual HTTP call or Railway Cron schedule), agents scan the GitHub repo for recent commits, group them by area of the codebase, and post a structured summary to Slack — what shipped, what's in progress, and patterns worth attention. If nothing shipped, a heartbeat message is posted so the channel stays active. Zero manual standup prep.

### 3. Slack Q&A — Any Team Member

Any developer types `/leadsync TICKET-123 Should I use a new table or extend users?` in Slack. LeadSync classifies the question and responds differently:


| Question Type                                           | Behavior                                                                                                                       |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Implementation** ("Should I...", "Which approach...") | Applies the tech lead's Google Docs preferences for that ticket's category, gives an opinionated recommendation with tradeoffs |
| **Progress** ("What's been done...")                    | Summarizes completed work from same-label tickets, cites ticket keys                                                           |
| **General** ("What is this ticket about?")              | Returns factual ticket info without injecting opinions                                                                         |


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

### 5. Jira PR Auto-Link — GitHub Webhook

Runs automatically alongside WF4 on every PR opened or reopened against `main`. No extra configuration needed.

- **Extracts the Jira ticket key** from the PR title or branch name (e.g., `LEADS-42`)
- **Posts a comment on the Jira ticket** with the PR URL and number so the ticket is immediately traceable to code
- **Transitions the Jira ticket to "In Review"** automatically — no manual status drag needed
- **If no Jira key is found**, posts a warning comment on the GitHub PR reminding the author to reference a ticket

This closes the loop between GitHub and Jira without any developer action.

### 6. Done Ticket Implementation Scan — Jira Webhook

Triggers when a Jira ticket is transitioned to **Done** status. Two agents pick up the work:

- **Implementation Scanner** — searches GitHub commit history and merged PRs on `main` for code changes that match the ticket key and summary
- **Implementation Summarizer** — distills the findings into a structured `IMPLEMENTATION_SUMMARY` and `FILES_CHANGED` list
- **Posts the summary as a Jira comment** on the completed ticket — a permanent, searchable record of what was built and where

This gives the team an automatic retrospective artifact for every shipped ticket, useful for onboarding, audits, and future context retrieval.

---

## Tech Lead Configuration

LeadSync is configured through **Google Docs** — one document per category. The tech lead writes coding rules, architectural preferences, and team-specific non-negotiables directly in Google Docs. These are fetched live on every workflow run (no restart or redeploy needed).

### Google Docs (per category)

| Label      | Env Variable for Doc ID          | Example Content |
| ---------- | -------------------------------- | --------------- |
| `backend`  | `LEADSYNC_BACKEND_PREFS_DOC_ID`  | Idempotent endpoints, input validation, async everywhere, rate limit annotations |
| `frontend` | `LEADSYNC_FRONTEND_PREFS_DOC_ID` | Accessible UI states, component reuse, critical user flow tests |
| `database` | `LEADSYNC_DATABASE_PREFS_DOC_ID` | Additive migrations, indexed queries, rollback validation |

The matching category is resolved from the Jira ticket's labels and components (defaults to `backend`).

Rules and preferences are automatically injected into Workflow 1 (prompt generation) and Workflow 3 (Slack Q&A reasoning).

---

## Tech Stack


| Layer        | Technology                       | Purpose                                                  |
| ------------ | -------------------------------- | -------------------------------------------------------- |
| API          | **FastAPI**                      | Webhook endpoints, async request handling                |
| AI Agents    | **CrewAI**                       | Multi-agent sequential workflows (max 3 agents per crew) |
| LLM          | **Gemini 2.5 Flash** via LiteLLM | Reasoning, summarization, prompt generation              |
| Integrations | **Composio**                     | Unified SDK for Jira, GitHub, Slack, Google Docs         |
| Memory       | **SQLite**                       | Event log, Q&A history, leader rules, digest tracking    |
| Deploy       | **Railway** + **ngrok**          | Production hosting + local webhook tunneling             |
| Language     | **Python 3.11+**                 |                                                          |


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


| Endpoint           | Method | Trigger                                                        |
| ------------------ | ------ | -------------------------------------------------------------- |
| `/health`          | GET    | Health check                                                   |
| `/webhooks/jira`   | POST   | Jira webhook — WF1 (ticket created/updated) or WF6 (→ Done)   |
| `/webhooks/github` | POST   | GitHub webhook — WF4 (PR description) + WF5 (Jira auto-link)  |
| `/digest/trigger`  | POST   | Manual or scheduled digest (WF2)                               |
| `/slack/commands`  | POST   | `/leadsync TICKET-KEY question` (WF3)                          |


---

## Project Structure

```
leadsync/
├── src/
│   ├── main.py                 # FastAPI app + all endpoints
│   ├── shared.py               # LLM factory, env helpers, Composio client
│   ├── prefs.py                # Google Docs preference loading
│   ├── leadsync_crew.py        # WF1 public wrapper
│   ├── digest_crew.py          # WF2 public wrapper
│   ├── slack_crew.py           # WF3 public wrapper
│   ├── pr_review_crew.py       # WF4 public wrapper
│   ├── jira_link_crew.py       # WF5 public wrapper (Jira PR auto-link)
│   ├── done_scan_crew.py       # WF6 public wrapper (Done ticket scan)
│   ├── workflow1/              # Ticket Enrichment (3 agents)
│   ├── workflow2/              # End-of-Day Digest (3 agents)
│   ├── workflow3/              # Slack Q&A (3 agents)
│   ├── workflow4/              # PR Auto-Description (1 agent + rules)
│   ├── workflow5/              # Jira PR Auto-Link (rule engine)
│   ├── workflow6/              # Done Ticket Scan (2 agents)
│   ├── common/                 # Model retry, tool helpers, text extraction
│   └── memory/                 # SQLite schema, read/write/query
├── demo/
│   └── fastapi_backend/        # Sample project for PR auto-description demo
├── config/                     # Tech lead context defaults
├── tests/
└── documentation/
```

---

