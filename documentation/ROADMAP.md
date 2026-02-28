# LeadSync — Hackathon Roadmap (Checkbox Edition)

Use this file as the live execution board.

## How To Use

- [ ] Mark each completed task immediately by changing `[ ]` to `[x]`.
- [ ] If scope or implementation decisions change, update this file in the same commit.
- [ ] Keep owner boundaries strict:
  - Dev 1 = API + integration + deploy
  - Dev 2 = crew logic + content + tests
- [ ] Do not add features not listed here unless both devs agree and record it in `Decision Log`.

## Decision Log (Editable As We Go)

- [x] Decision recorded: `src/main.py` intentionally exceeds the 150-line guideline. CLAUDE.md §8 (150-line limit) conflicts with §4 ("All endpoints in main.py. No router splitting."). Both rules cannot be satisfied simultaneously given the number of required endpoints. Ruling: the no-router-splitting rule takes precedence for this hackathon; the line limit is waived for main.py only.
- [x] Decision recorded: `src/prefs.py` added as a fourth source module (alongside the three crew files) to provide shared file I/O for tech lead preferences. This is a net-new module outside the original three-workflow crew structure — both developers agreed this is the correct layer for shared file access, not inline in any single crew file.
- [x] Decision recorded: Slack Q&A now uses conditional preference injection. `QUESTION_TYPE` is classified in retrieval output and team preferences are applied only for implementation questions; general questions return factual ticket info.
- [x] Decision recorded: Workflow 1 same-label historical progress is written in Jira comments only (`### Previous Progress (Same Label)`), not in the description body.
- [x] Decision recorded: Same-label precedent retrieval window increased from 5 to 10 completed tickets for richer demo context.
- [x] Decision recorded: Workflow 1 Jira comment/description write-back is now plain-text and technical (no markdown heading markers), focused on implementation guidance rather than ticket-style summarization.
- [x] Decision recorded: Hybrid SQLite memory layer added for hackathon context continuity. `events` + `memory_items` are now persisted in a lightweight local DB and queried during Slack Q&A; memory failures are best-effort and do not block primary workflow responses.
- [x] Decision recorded: Tech lead preferences now use Google Docs as the only source of truth. Workflow 1 and Workflow 3 fetch category-specific docs (`frontend`/`backend`/`database`) via Composio GOOGLEDOCS tools on every run; `/slack/prefs` is deprecated.
- [x] Decision recorded: Agent-scannability cleanup refactor approved. Workflow logic was split into focused subpackages (`src/workflow1`, `src/workflow2`, `src/workflow3`) plus shared internals (`src/common`, `src/memory`) while preserving legacy module entrypoints for compatibility.
- [x] Decision recorded: Workflow 2 scheduling uses Railway Cron + secured `POST /digest/trigger` (`X-LeadSync-Trigger-Token`) with 60-minute default lookback and SQLite idempotency lock keys to avoid duplicate hourly Slack posts.
- [x] Decision recorded: Workflow 2 now requires explicit repository targeting (`repo_owner` + `repo_name`) via trigger payload or env fallback (`LEADSYNC_GITHUB_REPO_OWNER`, `LEADSYNC_GITHUB_REPO_NAME`) to avoid ambiguous GitHub-tool prompting during demo runs.
- [x] Decision recorded: Workflow 2 now emits a guaranteed hourly heartbeat digest line when no meaningful commits are detected, so demo Slack activity remains visible every scheduled run.
- [x] Decision recorded: Workflow 1 now requires GitHub context during ticket enrichment. Repo targeting uses env vars (`LEADSYNC_GITHUB_REPO_OWNER`, `LEADSYNC_GITHUB_REPO_NAME`), and the attached prompt includes a dedicated `## Key Files` section extracted from GitHub-related-file analysis.
- [x] Decision recorded: Shared kickoff retry now handles transient empty LLM responses (`Invalid response from LLM call - None or empty.`) with one same-model retry and applies `flash-lite -> flash` fallback for resilient scheduled runs.

---

## Phase 0 — Environment + Baseline

### Dev 1 (API & Integration)
- [ ] `composio whoami` succeeds.
- [ ] Verify JIRA toolkit tools are available for active `COMPOSIO_USER_ID`.
- [ ] Verify GITHUB toolkit tools are available for active `COMPOSIO_USER_ID`.
- [ ] Verify SLACK toolkit tools are available for active `COMPOSIO_USER_ID`.
- [ ] Confirm `.env` contains: `COMPOSIO_API_KEY`, `GEMINI_API_KEY` (or `GOOGLE_API_KEY`), `SLACK_CHANNEL_ID`, `COMPOSIO_USER_ID`.
- [ ] Run app locally: `uvicorn src.main:app --reload`.
- [x] Confirm `GET /health` returns `{"status":"ok"}`.

### Dev 2 (Crew Logic & Content)
- [x] `src/shared.py` exports `_required_env`, `build_llm`, `build_tools`, `CrewRunResult`.
- [x] `templates/backend-ruleset.md` is present and usable.
- [x] `templates/frontend-ruleset.md` is present and usable.
- [x] `templates/db-ruleset.md` is present and usable.
- [x] `config/tech-lead-context.md` is present with realistic team guidance.
- [x] All crew files use shared helpers from `src/shared.py` (no duplicate env/tool builders).

---

## Phase 1 — Workflow 1 (Jira Ticket Enrichment)

### Dev 2 (Crew)
- [x] `src/leadsync_crew.py` runs 3-agent sequential flow with `verbose=True`.
- [x] Ruleset template is selected by ticket label (`backend`/`frontend`/`database`) with safe fallback.
- [x] Generated output is one file only: `prompt-[ticket-key].md`.
- [x] Prompt structure includes:
  - [x] `## Task`
  - [x] `## Context`
  - [x] `## Key Files`
  - [x] `## Constraints`
  - [x] `## Implementation Rules`
  - [x] `## Expected Output`
- [x] Workflow 1 gatherer uses GitHub tools to identify ticket-related key files for the attachment prompt.
- [x] Jira propagation updates description + adds comment + attaches prompt file.
- [x] Crew kickoff has try/except with readable logs.
- [x] Model fallback logic for `-latest` + `NOT_FOUND` is implemented.

### Dev 1 (Endpoint + E2E)
- [x] `POST /webhooks/jira` endpoint works from real payload.
- [x] Endpoint returns `{"status":"processed","model":...,"result":...}` on success.
- [x] Missing required env returns `HTTP 400`.
- [x] Crew failure returns `HTTP 500`.
- [ ] Golden payload test confirms Jira ticket is enriched and file attached.

---

## Phase 2 — Workflow 2 (Digest to Slack)

### Dev 2 (Crew)
- [x] `src/digest_crew.py` exists and uses 3-agent sequential flow with `verbose=True`.
- [x] GitHub scan focuses on main branch changes for recent window.
- [x] Digest output groups changes by area/theme.
- [x] Slack posting uses Composio SLACK tools only.
- [x] Crew kickoff has try/except with readable logs.
- [x] Model fallback logic for `-latest` + `NOT_FOUND` is implemented.

### Dev 1 (Endpoint + E2E)
- [x] `POST /digest/trigger` endpoint calls `run_digest_crew()`.
- [x] Endpoint success response shape is correct.
- [x] Missing required env returns `HTTP 400`.
- [x] Crew failure returns `HTTP 500`.
- [ ] End-to-end test confirms Slack digest message is posted.

---

## Phase 3 — Workflow 3 (Slack Q&A)

### Dev 2 (Crew)
- [x] `src/slack_crew.py` exists and uses 3-agent sequential flow with `verbose=True`.
- [x] Context retrieval pulls relevant Jira ticket context.
- [x] Reasoning uses category-specific Google Docs preferences loaded through Composio (`GOOGLEDOCS_GET_DOCUMENT_PLAINTEXT`).
- [x] Slack response behavior is conditional: factual ticket answers for GENERAL questions, opinionated guidance for IMPLEMENTATION questions.
- [x] Crew kickoff has try/except with readable logs.
- [x] Model fallback logic for `-latest` + `NOT_FOUND` is implemented.
- [x] Robustness enhancement: include precedent from last 10 completed same-category Jira tickets.

### Dev 1 (Endpoint + E2E)
- [x] `POST /slack/commands` supports Slack form payload (`text`) and JSON test payload.
- [x] Slash command request receives immediate success response (avoid Slack timeout).
- [ ] Crew runs successfully after command and posts to Slack.
- [x] Endpoint returns `HTTP 400` for missing/empty ticket input.
- [x] Endpoint returns `HTTP 500` for crew failure.
- [ ] End-to-end test in Slack command verifies threaded or channel response appears.

---

## Phase 3b — Workflow 4 (PR Auto-Description)

### Dev 2 (Crew)
- [x] `src/pr_review_crew.py` runs PR description writer agent with `verbose=True`.
- [x] Webhook payload parsing extracts PR metadata + Jira key from branch/title/body.
- [x] Changed files fetched via Composio GitHub tools with multi-fallback strategy (PR files → commit compare → individual commits → raw `.diff`).
- [x] AI-generated sections: summary, implementation details, suggested validation.
- [x] Deterministic fallback when AI generation fails (diff signal extraction for routes, functions, tests, query patterns).
- [x] Enrichment block is idempotent (HTML comment markers, upsert on re-run).
- [x] Manual PR description content preserved above/below enrichment block.

### Dev 1 (Endpoint + E2E)
- [x] `POST /webhooks/github` endpoint works from real GitHub webhook payload.
- [x] Endpoint returns `{"status":"processed","model":...,"result":...}` on success.
- [x] Unsupported actions (e.g., `closed`) are skipped gracefully.
- [x] Missing PR metadata returns `HTTP 400`.
- [x] Crew failure returns `HTTP 500`.
- [ ] Golden payload test confirms PR description is enriched on GitHub.

---

## Phase 4 — Testing + Quality Gate

### Dev 2 (Primary Owner)
- [x] `tests/test_shared.py` covers required env + model defaults.
- [x] `tests/test_leadsync_crew.py` covers happy path + model fallback.
- [x] `tests/test_digest_crew.py` covers happy path + model fallback.
- [x] `tests/test_slack_crew.py` covers parse + happy path + model fallback.
- [x] `tests/test_main.py` covers health + all endpoint success/error paths.
- [x] All tests pass: `pytest -q`.
- [x] Coverage target met: `pytest --cov=src --cov-report=term-missing -q` >= 60%. (actual: 92%)

### Cross-Cut Checks
- [x] No raw Jira/GitHub/Slack API calls outside Composio.
- [x] No `print()` in `src/`; rely on logging + verbose crew traces.
- [x] Secrets are not committed.
- [x] Response schema consistency maintained across endpoints.

---

## Phase 5 — Integrations + Demo Delivery

### Dev 1 (Primary Owner)
- [ ] ngrok tunnel running and stable for local demo.
- [ ] Jira webhook points to `<public-url>/webhooks/jira`.
- [ ] GitHub webhook points to `<public-url>/webhooks/github` (PR events: opened, reopened, synchronize, ready_for_review).
- [ ] Slack slash command `/leadsync` points to `<public-url>/slack/commands`.
- [ ] Slack app/bot has required scopes and channel access.
- [ ] Railway deploy configured with all required env vars.
- [ ] Railway `/health` verified.
- [ ] Jira + Slack integrations switched from ngrok URL to Railway URL when ready.

### Full E2E Demo Checklist
- [ ] Workflow 1 demo: new Jira ticket -> enriched ticket + prompt attachment.
- [ ] Workflow 2 demo: digest trigger -> Slack summary posted.
- [ ] Workflow 3 demo: `/leadsync` question -> reasoned Slack answer posted.
- [ ] Workflow 4 demo: open PR -> description auto-populated with summary + implementation details.
- [ ] Logs are readable and useful during all demo beats.

---

## Phase 6 — Robustness Enhancements (Hackathon Scope)

### Jira History Context (Dev 2)
- [x] Define same-category ticket selection rule.
- [x] Retrieve last 10 completed tickets in category.
- [x] Summarize patterns from completed tickets (approach, pitfalls, constraints).
- [x] Inject this precedent context into Workflow 3 reasoning prompt.
- [x] Add/extend tests for this behavior.

### GitHub Intelligence Upgrade (Dev 1 + Dev 2)
- [x] Define daily analysis trigger approach.
- [x] Implement scheduled daily repository analysis.
- [x] Keep on-demand endpoint/command for recent code-change questions.
- [x] Reuse Workflow 2 primitives where possible.
- [x] Add tests and failure handling for both scheduled and on-demand paths.

### Hybrid Memory Layer (Dev 1 + Dev 2)
- [x] Add SQLite-backed memory module with schema bootstrap for `events` and `memory_items`.
- [x] Persist curated memory writes from Workflow 1 (ticket enrichment), Workflow 2 (digest areas), and Workflow 3 (Slack Q&A).
- [x] Inject memory query context into Workflow 3 prompts (ticket memory, recent digests, similar prior Q&A by label/component).
- [x] Add startup memory initialization in FastAPI with best-effort failure handling.
- [x] Add tests for memory store schema/read/write/query and workflow integration behavior.

---

## Phase 7 — Tech Lead Preferences (Google Docs Source)

> **Context:** Fast-pace startup environment where developers change seats/departments frequently.
> The tech lead needs a way to maintain live coding preferences (style, constraints, architectural rules)
> that are automatically injected into AI responses without editing files on disk.

### Dev 1 (Endpoint + Integration)
- [x] Added required env vars for fixed Google Docs IDs: `LEADSYNC_FRONTEND_PREFS_DOC_ID`, `LEADSYNC_BACKEND_PREFS_DOC_ID`, `LEADSYNC_DATABASE_PREFS_DOC_ID`.
- [x] Deprecated `POST /slack/prefs` and replaced mutating behavior with HTTP 410 guidance (except Slack `ssl_check=1`).
- [x] Updated `.env.example` and `documentation/quickstart.md` with Google Docs setup details.

### Dev 2 (Module + Refactor)
- [x] Replaced file-based preference loader with Google Docs loader in `src/prefs.py`.
- [x] Added category resolver (`frontend`/`backend`/`database`) and fixed-env doc ID resolver.
- [x] Added strict Google Docs plain-text fetch (`GOOGLEDOCS_GET_DOCUMENT_PLAINTEXT`) with hard-fail behavior on missing tool/env/empty result.
- [x] Integrated category-specific Google Docs preferences into Workflow 1 reasoner prompt generation.
- [x] Integrated category-specific Google Docs preferences into Workflow 3 implementation guidance path.
- [x] Updated tests: `test_prefs.py`, `test_leadsync_crew.py`, `test_slack_crew.py`, `test_main.py` for Google Docs source and `/slack/prefs` deprecation.

---

## Phase 8 — Workflow 5 (Jira-GitHub PR Auto-Link)

### Dev 1 (API & Integration)
- [ ] `src/workflow5/` package with `__init__.py`, `runner.py`, `ops.py`
- [ ] `src/jira_link_crew.py` public wrapper
- [ ] `src/main.py` fan-out: WF5 runs alongside WF4 in `github_webhook`, non-blocking
- [ ] `tests/test_jira_link_crew.py` — full unit coverage for runner, ops, wrapper, and endpoint layers

---

## Checkpoint Summary (Mark When Fully Verified)

- [ ] Checkpoint A: Local environment + base integrations verified.
- [ ] Checkpoint B: Workflow 1 production-like behavior verified.
- [ ] Checkpoint C: All 4 workflows execute without exceptions.
- [x] Checkpoint D: Tests green with target coverage. (111 tests passing, 92% coverage)
- [ ] Checkpoint E: Live deploy + external integrations verified.
- [ ] Checkpoint F: Demo rehearsal complete and stable.

---

## Status Log

| Date | Owner | Update |
|------|-------|--------|
| 2026-02-28 | Dev 2 | Hardened shared crew reliability for transient provider failures: `src/common/model_retry.py` now retries once on empty LLM responses and falls back `flash-lite` to `flash` when needed; added `tests/test_model_retry.py` and revalidated full suite (`pytest -q`: 107 passing). |
| 2026-02-28 | Dev 2 | Hardened Workflow 1 Jira write-back reliability: added deterministic `JIRA_EDIT_ISSUE` + `JIRA_ADD_COMMENT` calls after prompt generation, added strict tool-response failure detection (`src/common/tool_response.py`), and upgraded attachment handling to raise on failure payloads (not only exceptions); expanded tests and revalidated (`pytest -q`: 111 passing, coverage: 92%). |
| 2026-02-28 | Dev 1 + Dev 2 | Implemented Workflow 1 GitHub related-file integration: wired GitHub repo env targeting into Jira enrichment runs, merged Jira+GitHub tooling for gatherer context, enforced hard-fail when GitHub context is unavailable, added deterministic key-file extraction contract (`KEY_FILE: ...`), and upgraded prompt artifact requirements with a dedicated `## Key Files` section plus parser tests. |
| 2026-02-28 | Dev 1 + Dev 2 | Fixed Workflow 2 GitHub targeting ambiguity that caused runtime "provide repository owner and name" responses: added explicit repo target propagation (`repo_owner`/`repo_name`) from `/digest/trigger` payload with env fallback, updated scanner prompt contract, expanded tests, and documented Railway cron env requirements. |
| 2026-02-28 | Dev 1 + Dev 2 | Finalized demo-hourly digest behavior: Workflow 2 prompt contract now forces explicit no-commit heartbeat output (`AREA: general | SUMMARY: No meaningful commits ...`), quickstart now includes dedicated Slack channel setup/invite flow + manual verification call, and tests were expanded for quiet-hour behavior. |
| 2026-02-28 | Dev 2 | Finalized agent-scannability refactor after concurrent edits: resolved duplicate helper collisions in `shared.py` and `src/memory/write.py`, preserved Workflow 2 schedule/idempotency interfaces, kept compatibility facades on legacy module paths, and revalidated suite (`pytest -q`: 94 passing, coverage: 92%). |
| 2026-02-28 | Dev 1 + Dev 2 | Implemented Workflow 2 scheduled digest readiness: added secure trigger support for `POST /digest/trigger` with optional shared token header, configurable digest window (`LEADSYNC_DIGEST_WINDOW_MINUTES`), run metadata (`run_source`, `bucket_start_utc`), SQLite idempotency locks (`idempotency_locks`) to suppress duplicate scheduled buckets, and updated tests/docs (`pytest -q`: 94 passing). |
| 2026-02-28 | Dev 2 | Implemented agent-scannability cleanup refactor: split oversized workflow files into dedicated subpackages, centralized shared helpers (task-output extraction, model fallback retry, token/tool lookup), split memory internals into `src/memory/*` with `src/memory_store.py` facade, split Jira history/prefs into core + facade modules, and moved FastAPI startup initialization to lifespan; tests remain green (81 passing, 92% coverage). |
| 2026-02-28 | Dev 1 + Dev 2 | Implemented full Google Docs preference migration: added fixed category doc ID env vars, replaced local file/slash-command preference source with live GOOGLEDOCS fetches in Workflow 1 and 3, deprecated `/slack/prefs` to HTTP 410 guidance, updated quickstart/env docs, and expanded tests (81 passing, 85% coverage). |
| 2026-02-28 | Dev 2 | Updated `AGENTS.md` to document hybrid SQLite memory usage (shared helper usage, best-effort behavior, env vars) and aligned "what's cut" with current scope (no external managed DB). |
| 2026-02-28 | Dev 2 | Implemented hybrid SQLite memory layer: added `src/memory_store.py`, wired best-effort memory writes across all workflows, injected query-time memory context into Slack Q&A, added startup DB initialization, and expanded tests (`test_memory_store`, workflow memory integration assertions). |
| 2026-02-28 | Dev 2 | Refined Workflow 1 Jira write-back instructions to be plain-text and technical (non-markdown, non-meta), added explicit repository file/module targeting guidance when GitHub tools are available, and expanded same-label history context to include completed ticket description excerpts. |
| 2026-02-28 | Dev 1 | Added `railway.json` with explicit Railpack start command (`uvicorn src.main:app --host 0.0.0.0 --port $PORT`) and `/health` healthcheck to resolve `railway up` auto-detection failure. |
| 2026-02-28 | Dev 2 | Added minimal backend/frontend/db ruleset template files under `templates/` and improved Workflow 1 ruleset matching to select related rulesets from Jira labels/components; added tests for matching behavior. |
| 2026-02-28 | Dev 2 | Implemented conditional preference injection in Workflow 3 (`QUESTION_TYPE` classification + conditional reasoning branch) and added 2 Slack crew prompt tests; suite now 51 passing tests. |
| 2026-02-28 | Dev 2 | Implemented Workflow 1 deterministic prompt artifact flow: generates `artifacts/workflow1/prompt-[ticket-key].md` with required sections and attaches via `JIRA_ADD_ATTACHMENT`; added tests for section structure and attachment failure handling. |
| 2026-02-28 | Dev 2 | Fixed Workflow 1 Jira attachment bug where filename-only upload failed; now passes absolute path for both `local_file_path` and `file_to_upload`, adds explicit file existence check, and extends test coverage. |
| 2026-02-28 | Dev 2 | Implemented same-label Jira history integration: Workflow 1 now injects same-label precedent and requires `### Previous Progress (Same Label)` in Jira comment output; Workflow 3 now includes this history and supports `QUESTION_TYPE: PROGRESS`; added shared `jira_history` helper tests and crew prompt assertions. |
| 2026-02-28 | Dev 2 | Improved demo-facing wording for Workflow 1/3 responses (explicit previous-progress summary template, removed meta 'ticket enriched' style language), and expanded same-label retrieval window to latest 10 completed tickets with updated tests. |
