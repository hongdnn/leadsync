# Sponsor Tool Integration — LeadSync

> How LeadSync uses **Composio** and **CrewAI** as core infrastructure to deliver an agentic context engine for developer workflows.

---

## Composio

### What It Does for Us

Composio is our **single integration layer** for every external service LeadSync touches. Instead of writing raw API clients for Jira, GitHub, Slack, and Google Docs, we use Composio to provision authenticated tool sets that CrewAI agents call directly during execution.

### Integration Architecture

```
FastAPI Endpoint
  └─► Crew Wrapper (e.g. leadsync_crew.py)
        └─► build_tools(user_id, toolkits=["JIRA", "GITHUB", ...])
              └─► Composio(provider=CrewAIProvider())
                    └─► composio.tools.get(user_id=..., toolkits=[...])
                          └─► Returns tool objects passed directly to CrewAI Agent(tools=...)
```

All tool construction goes through a single shared builder (`src/shared.py:build_tools`) that:
1. Validates the `COMPOSIO_API_KEY` is present.
2. Instantiates `Composio(provider=CrewAIProvider())` — the CrewAI-native provider.
3. Fetches tools by **toolkit name** (broad) or **specific tool name** (narrow), depending on the workflow's needs.

### Toolkits Used

| Toolkit | Workflows | Purpose |
|---------|-----------|---------|
| **JIRA** | WF1, WF3, WF5, WF6 | Read tickets, edit descriptions, add comments, add attachments, search via JQL, transition statuses |
| **GITHUB** | WF1, WF2, WF4, WF5, WF6 | List commits, list PR files, compare commits, update PR descriptions, create issue comments |
| **SLACK** | WF2, WF3 | Post digests to channels, send threaded replies to developer questions |
| **GOOGLEDOCS** | WF1, WF3 | Load team coding preferences from shared Google Docs per category (frontend, backend, database) |

### Fine-Grained Tool Selection

We use two patterns depending on the workflow:

**Toolkit-level** — when agents need broad access:
```python
github_tools = build_tools(user_id=user_id, toolkits=["GITHUB"])
slack_tools  = build_tools(user_id=user_id, toolkits=["SLACK"])
```

**Specific tool names** — when agents need only targeted actions:
```python
# Workflow 1: Only the Jira actions the Context Gatherer and Propagator need
jira_tools = build_tools(
    user_id=user_id,
    tools=["JIRA_GET_ISSUE", "JIRA_EDIT_ISSUE", "JIRA_ADD_COMMENT",
           "JIRA_ADD_ATTACHMENT", "JIRA_SEARCH_FOR_ISSUES_USING_JQL_POST"],
)

# Workflow 4: Only the GitHub actions needed for PR enrichment
github_tools = build_tools(
    user_id=user_id,
    tools=["GITHUB_LIST_PULL_REQUEST_FILES", "GITHUB_COMPARE_TWO_COMMITS",
           "GITHUB_LIST_PULL_REQUEST_COMMITS", "GITHUB_UPDATE_A_PULL_REQUEST", ...],
)
```

This keeps each agent's tool surface minimal — agents only see the actions they are supposed to use.

### Where Composio Appears in the Codebase

| File | Role |
|------|------|
| `src/shared.py` | Central `build_tools()` function — single source of truth for all Composio tool construction |
| `src/tools/jira_tools.py` | Defines `REQUIRED_JIRA_TOOLS` list and `get_agent_tools()` for Workflow 1 |
| `src/integrations/composio_provider.py` | Backward-compatible facade delegating to `build_tools()` |
| `src/leadsync_crew.py` | Builds JIRA + GITHUB + GOOGLEDOCS tools for ticket enrichment |
| `src/digest_crew.py` | Builds GITHUB (limit=10) + SLACK tools for daily digest |
| `src/slack_crew.py` | Builds JIRA + GOOGLEDOCS + SLACK tools for Q&A |
| `src/pr_review_crew.py` | Builds specific GITHUB tools for PR description writing |
| `src/done_scan_crew.py` | Builds GITHUB + JIRA tools for implementation scanning |
| `src/jira_link_crew.py` | Builds JIRA + GITHUB tools for PR-to-ticket auto-linking |

### User Identity Management

All Composio calls pass a `user_id` (from `COMPOSIO_USER_ID` env var, default `"default"`), enabling per-user authentication scoping across every workflow.

---

## CrewAI

### What It Does for Us

CrewAI is our **multi-agent orchestration framework**. Every LeadSync workflow is a separate Crew with specialized agents that execute sequentially — each agent has a distinct role, and tasks chain their outputs so later agents build on earlier results.

### Crew Summary

| Crew | File | Agents | Tasks | Purpose |
|------|------|--------|-------|---------|
| **WF1 — Ticket Enrichment** | `src/leadsync_crew.py` | Context Gatherer, Intent Reasoner, Propagator | 3 | Jira ticket fires webhook → gather context → generate implementation prompt → write back to Jira |
| **WF2 — End-of-Day Digest** | `src/digest_crew.py` | GitHub Scanner, Digest Writer, Slack Poster | 3 | Scan recent commits → summarize by area → post to Slack |
| **WF3 — Slack Q&A** | `src/slack_crew.py` | Context Retriever, Solution Reasoner, Slack Responder | 3 | Fetch Jira context → reason about the question → post answer to Slack thread |
| **WF4 — PR Auto-Description** | `src/pr_review_crew.py` | PR Description Writer | 1 | Analyze PR diffs → generate structured description → update GitHub PR |
| **WF6 — Done Scan** | `src/done_scan_crew.py` | Implementation Scanner, Implementation Summarizer | 2 | When ticket moves to Done → find related commits/PRs → summarize what was built |

All crews use `Process.sequential` and `verbose=True` for full execution logging.

### Agent Design Pattern

Every agent follows the same structure:

```python
agent = Agent(
    role="Context Gatherer",
    goal="Collect Jira and GitHub context needed to implement the issue correctly.",
    backstory="You are responsible for finding relevant context from Jira and recent commits.",
    verbose=True,
    tools=composio_tools,  # Only agents that need external access get tools
    llm=model,             # Gemini via LiteLLM
)
```

Key design decisions:
- **Reasoner agents get no tools** — they operate purely on outputs from prior tasks, keeping them focused on synthesis rather than data fetching.
- **Tool agents get only the Composio tools they need** — the Context Gatherer gets Jira + GitHub tools; the Slack Poster gets only Slack tools.
- **All agents share the same LLM** (`gemini/gemini-2.5-flash` via LiteLLM), configurable through a single env var.

### Task Chaining with Context Dependencies

Tasks chain their outputs using CrewAI's `context` parameter:

```python
gather_task = Task(description=..., agent=gatherer)

reason_task = Task(
    description=...,
    agent=reasoner,
    context=[gather_task],   # Receives gatherer's output
)

propagate_task = Task(
    description=...,
    agent=propagator,
    context=[reason_task],   # Receives reasoner's output
)
```

This ensures each agent builds on the previous agent's work in a structured pipeline:
- **WF1:** Gather context → Reason about implementation → Write back to Jira
- **WF2:** Scan commits → Write digest → Post to Slack
- **WF3:** Retrieve ticket → Reason about answer → Respond in Slack
- **WF6:** Scan for implementations → Summarize findings

### Runtime Dependency Injection

Each workflow defines a `Runtime` dataclass that injects CrewAI classes and business logic functions. This allows complete test mocking without monkey-patching:

```python
@dataclass
class Workflow1Runtime:
    Agent: Any          # crewai.Agent
    Task: Any           # crewai.Task
    Crew: Any           # crewai.Crew
    Process: Any        # crewai.Process
    resolve_preference_category: Callable[...]
    load_preferences_for_category: Callable[...]
    # ... other business dependencies
```

Production code passes real CrewAI classes; tests pass mocks. This pattern is used across WF1, WF2, WF3, and WF6.

### Model Fallback & Resilience

All crews are executed through `kickoff_with_model_fallback()` (`src/common/model_retry.py`), which wraps `crew.kickoff()` with automatic retry logic:

1. **First attempt** with the configured model.
2. On failure: detect the error type and select a fallback:
   - Model alias with `-latest` suffix → strip suffix and retry.
   - `flash-lite` model unavailable → fall back to `flash`.
   - `2.5-flash` empty response → fall back to `2.0-flash`.
3. **Dynamically reassign** the fallback model to all agents (`agent.llm = fallback_model`) and retry.

```python
result, used_model = kickoff_with_model_fallback(
    crew=crew,
    model=model,
    agents=[gatherer, reasoner, propagator],
    logger=logger,
    label="LeadSync",
)
```

This ensures every workflow can recover from transient model issues without manual intervention.

### Output Extraction

A shared utility (`src/common/task_output.py:extract_task_output`) normalizes CrewAI task output across different response formats:

```python
def extract_task_output(task: Any) -> str:
    output = getattr(task, "output", None)
    # Tries: output as string → output.raw → output.result
```

This is used by every workflow to read intermediate task results for post-processing (e.g., extracting the generated prompt from the Reasoner task before writing it back to Jira).

### Where CrewAI Appears in the Codebase

| File | Role |
|------|------|
| `src/leadsync_crew.py` | WF1 crew wrapper — assembles agents, tools, and kicks off enrichment |
| `src/digest_crew.py` | WF2 crew wrapper — assembles digest pipeline |
| `src/slack_crew.py` | WF3 crew wrapper — assembles Q&A pipeline |
| `src/pr_review_crew.py` | WF4 crew wrapper — single-agent PR writer |
| `src/done_scan_crew.py` | WF6 crew wrapper — assembles implementation scan |
| `src/workflow1/crew_build.py` | WF1 internal — agent/task/crew construction |
| `src/workflow1/task_descriptions.py` | WF1 internal — structured task description templates |
| `src/workflow2/runner.py` | WF2 internal — agent/task/crew construction + execution |
| `src/workflow3/crew_build.py` | WF3 internal — agent/task/crew construction |
| `src/workflow3/runner.py` | WF3 internal — execution with memory integration |
| `src/workflow4/ai_writer.py` | WF4 internal — single-agent crew for PR descriptions |
| `src/workflow6/crew_build.py` | WF6 internal — agent/task/crew construction |
| `src/workflow6/runner.py` | WF6 internal — execution with memory integration |
| `src/common/model_retry.py` | Shared — `kickoff_with_model_fallback()` wrapping `crew.kickoff()` |
| `src/common/task_output.py` | Shared — `extract_task_output()` for normalized output reading |

---

## How They Work Together

```
Jira Webhook → FastAPI Endpoint
                 │
                 ├─► Composio builds authenticated tool sets (JIRA, GITHUB, GOOGLEDOCS)
                 │
                 ├─► CrewAI agents receive those tools
                 │     Agent 1: Context Gatherer  [tools: JIRA + GITHUB]
                 │     Agent 2: Intent Reasoner   [tools: none — pure reasoning]
                 │     Agent 3: Propagator         [tools: JIRA]
                 │
                 ├─► Crew.kickoff() runs the sequential pipeline
                 │     Task 1 output → feeds into Task 2 → feeds into Task 3
                 │
                 └─► Result: enriched Jira ticket with paste-ready implementation prompt
```

**Composio** handles all external service authentication and API abstraction.
**CrewAI** handles agent orchestration, task sequencing, and output chaining.

Together, they let us build 6 distinct agentic workflows — each with specialized agents, scoped tool access, and structured output — without writing a single raw API call or managing any inter-agent communication manually.
