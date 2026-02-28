# LeadSync — PROJECT_IDEA.md
> Coding agent context doc. Read this entirely before writing any code.

---

## What LeadSync Is

LeadSync is an agentic system that sits between a tech lead and their dev team. It removes the constant back-and-forth by doing three things automatically:

1. When a Jira ticket is created, agents enrich it with a ready-to-use AI prompt the developer can paste directly into their coding environment.
2. At the end of the day, an agent scans GitHub and posts a digest of what changed and overall progress to Slack.
3. When a developer asks a question in Slack about a specific ticket, an agent responds with reasoning from the tech lead's perspective — not a ticket summary, but actual judgment informed by rules and context the tech lead has defined upfront.

**Current implementation status (2026-02-28):**
- Basic Jira + Composio + Slack integration is working end-to-end for MVP flows.
- Workflow 3 already retrieves Jira context and returns reasoned LLM answers in Slack command flow.

---

## Three Distinct Workflows

### Workflow 1 — Ticket Enrichment (Auto-triggered)

**Trigger:** Jira webhook fires when a ticket is created or assigned.

**What happens:**
- Agent reads the ticket: title, minimal description, label, assignee.
- Based on the label, it loads the matching ruleset template (backend / frontend / database).
- Agent enriches the ticket in place: updates the title if vague, expands the description with relevant context inferred from the label + recent GitHub commits.
- Agent generates a single, self-contained AI prompt that a developer can copy-paste directly into their coding agent (Cursor, Claude Code, etc.) to complete the task. This is one file, not two. It contains the task, context, constraints, and rules baked together — the developer needs zero additional input.
- The prompt is attached to the Jira ticket as a comment or file attachment.

**Output in Jira:**
- Enriched ticket title and description (written by the agent, not the tech lead)
- One attached file: `prompt-[ticket-key].md` — ready to paste into a coding agent

---

### Workflow 2 — End-of-Day Digest (Manually triggered for demo)

**Trigger:** HTTP endpoint called manually during demo to simulate "end of day." No cron needed for hackathon.

**What happens:**
- Agent scans GitHub: all commits to main branch in the last 24 hours.
- Agent groups commits by theme / area of the codebase.
- Agent produces a natural-language summary: what changed, what's in progress, any patterns worth the tech lead's attention (e.g., multiple commits touching the same file, missing tests, etc.).
- Summary is posted as a Slack message to a designated channel.

**Output in Slack:**
- One message with a structured daily digest: changes grouped by area, brief interpretation, overall progress signal.

---

### Workflow 3 — Slack Q&A for Developers (Slash command)

**Trigger:** Developer types `/leadsync JIRA-123 [their question]` in Slack.

**What happens:**
- Agent retrieves the Jira ticket context.
- Agent reasons from the perspective of the tech lead — not summarizing the ticket, but applying the tech lead's judgment.
- The tech lead's judgment is informed by a "Tech Lead Context" config: a plain text document the tech lead fills in once, containing their architectural preferences, non-negotiables, common patterns the team should follow, and any ticket-specific notes. This config is stored server-side and injected into the agent's reasoning at query time.
- Agent replies in Slack with a direct, opinionated answer as if the tech lead wrote it.

**Example:**
- Developer asks: "Should I add a new table for this or extend the users table?"
- Agent answers based on the tech lead's defined preferences (e.g., "Prefer extending existing tables when adding fewer than 3 columns, per our schema minimalism rule") — not just restating the ticket.

**Output in Slack:**
- Threaded reply to the developer with a reasoned answer, not a summary.
- Planned robustness upgrade: include precedent context from the last 5 completed Jira tickets in the same category before final reasoning.

---

## Tech Lead Context Config

This is the key input that makes Workflow 3 non-trivial and demo-worthy.

The tech lead fills in a structured plain-text config (stored in the system) that contains:
- Architectural preferences ("we prefer async patterns everywhere")
- Per-label rules ("backend tickets: always consider rate limiting impact")
- Non-negotiables ("never introduce new global state")
- Team-specific context ("Alice is strong on DB, Bob owns the auth layer")
- Any freeform notes per ticket key that can be looked up at query time

This config is what separates the Slack agent from a dumb ticket summarizer — it gives the agent a point of view.

---

## Ruleset Templates (Label-Based)

Three templates stored as plain text files in the project:

**backend ruleset** — async patterns, API contract stability, load considerations, error handling standards

**frontend ruleset** — component boundaries, state management rules, accessibility requirements, testing standards

**database ruleset** — migration safety, indexing requirements, query performance standards, transaction rules

These are injected into the AI prompt generated in Workflow 1. They are also available to the Slack agent in Workflow 3 when reasoning about a ticket.

---

## Generated AI Prompt Structure (Workflow 1 output)

The single attached prompt file must contain everything a developer needs to hand off to a coding agent with zero additional input:

```
## Task
[What needs to be built — enriched from the ticket title/description]

## Context
[Recent commits to main that are relevant — summarized, not raw]
[Linked tickets if any]

## Constraints
[Inferred from label ruleset + tech lead config]
[What must not change or break]

## Implementation Rules
[From the label-matched ruleset template]

## Expected Output
[Code, tests, and any spec/doc updates required]
```

This replaces the old two-file approach. One file. Paste and go.

---

## Project Structure (Logical, Not Prescriptive)

```
leadsync/
├── workflows/
│   ├── ticket_enrichment     # Workflow 1 agents + logic
│   ├── daily_digest          # Workflow 2 agents + logic
│   └── slack_qa              # Workflow 3 agents + logic
├── templates/
│   ├── backend-ruleset.md
│   ├── frontend-ruleset.md
│   └── db-ruleset.md
├── config/
│   └── tech-lead-context.md  # Tech lead fills this in — drives Workflow 3
├── api/
│   └── main                  # HTTP endpoints: webhook, digest trigger, slack handler
└── .env
```

---

## API Endpoints Needed

| Endpoint | Trigger | Purpose |
|----------|---------|---------|
| `POST /webhooks/jira` | Jira webhook | Fires Workflow 1 |
| `POST /digest/trigger` | Manual HTTP call | Fires Workflow 2 (demo simulation of end-of-day) |
| `POST /slack/commands` | Slack slash command | Fires Workflow 3 |

---

## Demo Script (Live, ~4 minutes)

### Beat 1 — Ticket Enrichment (90 sec)
- Create a sparse Jira ticket: title "add rate limiting", label `backend`, assign to Alice. No description.
- Show the ticket as-is: minimal, unhelpful.
- Watch the backend logs: agents fire, GitHub is scanned, ruleset loaded, prompt generated.
- Refresh Jira: title is cleaner, description is written, one attachment `prompt-LEADS-1.md` is there.
- Open the file: a complete, paste-ready prompt. "Alice opens this, pastes into Claude Code, starts building."

### Beat 2 — End-of-Day Digest (45 sec)
- Hit `POST /digest/trigger` (curl or simple button in logs page).
- Watch logs: agent scans commits, groups changes, writes summary.
- Open Slack: message appears in channel with grouped digest and progress signal.
- "Every evening, the team sees what actually shipped — zero manual standup prep."

### Beat 3 — Developer Q&A in Slack (45 sec)
- Type `/leadsync LEADS-1 Should I extend the users table or create a new one?`
- Watch logs: agent retrieves ticket, loads tech lead context config, reasons.
- Reply appears in Slack: opinionated answer based on the tech lead's defined preferences.
- "This is the tech lead's judgment, available 24/7, without the ping."

---

## What's Cut (Do Not Re-Add)

- ❌ Two separate prompt + ruleset files — one prompt file only
- ❌ PR webhooks — main branch commits pulled on-demand
- ❌ Notion integration
- ❌ Custom UI or dashboard (logs page acceptable for demo readability)
- ❌ Nightly cron — digest is manually triggered for demo
- ❌ Any persistent database — flat files and in-memory state only
- ❌ LLM choice is not locked — to be determined during implementation

## Planned Extensions (Hackathon Scope)

1. Workflow 3 historical context enhancement:
   analyze the last 5 completed Jira tickets in the same category and feed that context into Slack Q&A responses.
2. GitHub intelligence enhancement:
   add daily scheduled repository analysis plus on-demand user-triggered summaries for "recent code changes" and task relation questions during the hackathon.
3. **Tech Lead Preferences System:**
   allow the tech lead to maintain a live preferences document that is automatically injected into AI responses. See below for full description.

---

## Tech Lead Preferences System

### Why It Exists

LeadSync targets fast-pace startup environments where developers frequently change seats or departments. A tech lead cannot be available 24/7 to answer implementation questions, and onboarding new developers to team conventions is slow. The preferences system makes the tech lead's judgment persistent and available on-demand — a document the tech lead maintains once and that informs every AI response automatically.

### What It Is

A plain text file (`config/tech-lead-context.md`) that the tech lead maintains with:
- Architectural preferences (async patterns, service layer conventions)
- Non-negotiables (no global state, no raw SQL)
- Per-label rules (backend: always rate limit; database: prefer extending tables)
- Team notes (who owns which layer)
- Quick rules added live via Slack command

The file is loaded at runtime (not cached) by Workflow 3, so every update is reflected in the next AI response with zero restart.

### How It Works

**Updating via Slack:** The tech lead types `/leadsync-prefs add "rule text"` in Slack. The command appends a new bullet to a dedicated `## Quick Rules (added via Slack)` section in `config/tech-lead-context.md`. Slack shows an ephemeral confirmation immediately.

**AI injection:** Every time a developer asks `/leadsync TICKET-X question`, the Slack Q&A crew loads the full preferences file and passes it to the Tech Lead Reasoner agent. The AI answers from the tech lead's defined perspective, not from generic knowledge.

### Scope (Hackathon)

- Add-only via Slack slash command (`/leadsync-prefs add "..."`)
- Preferences apply to Workflow 3 (Slack Q&A) only
- No authentication — single-tenant hackathon demo
- No deletion or versioning — append-only for simplicity

### Implementation

| Component | Description |
|-----------|-------------|
| `src/prefs.py` | `load_preferences()` and `append_preference(text)` |
| `POST /slack/prefs` | Slack slash command handler in `main.py` |
| `slack_crew.py` | Refactored to use `prefs.load_preferences()` |
| `tests/test_prefs.py` | Unit tests for the preferences module |

### Demo Beat (30 seconds)

1. Show current `config/tech-lead-context.md` — team's existing rules visible.
2. Type `/leadsync-prefs add "Never call sync DB from async handlers"` in Slack.
3. Slack confirms: "Preference added."
4. Ask `/leadsync LEADS-X Should I use a sync query here?`
5. AI answer cites the just-added rule — live, no restart needed.

---

## Coding Agent Rules

1. **Three workflows, three separate agent crews** — do not conflate them into one mega-flow.
2. **One output file per ticket** — `prompt-[ticket-key].md` — not two files.
3. **Tech Lead Context config is the reasoning backbone for Workflow 3** — it must be loaded and injected, not ignored.
4. **Slack Q&A must reason, not summarize** — the agent response should feel like a judgment call, not a lookup.
5. **Digest trigger is manual for demo** — an HTTP endpoint, not a scheduler.
6. **LLM layer is undecided** — do not hardcode any specific model or provider. Design so it can be swapped.
7. **No raw API calls** — use Composio for all Jira, GitHub, and Slack interactions.
8. **Verbose logging everywhere** — this is a demo, logs are part of the show.
9. **Templates are files** — loaded from `/templates/` at runtime.
10. **Tech Lead Context is a file** — loaded from `/config/tech-lead-context.md` at runtime.
