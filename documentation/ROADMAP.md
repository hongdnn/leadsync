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
  - [x] `## Constraints`
  - [x] `## Implementation Rules`
  - [x] `## Expected Output`
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
- [x] Reasoning uses `config/tech-lead-context.md`.
- [x] Slack response behavior is conditional: factual ticket answers for GENERAL questions, opinionated guidance for IMPLEMENTATION questions.
- [x] Crew kickoff has try/except with readable logs.
- [x] Model fallback logic for `-latest` + `NOT_FOUND` is implemented.
- [ ] Robustness enhancement: include precedent from last 5 completed same-category Jira tickets.

### Dev 1 (Endpoint + E2E)
- [x] `POST /slack/commands` supports Slack form payload (`text`) and JSON test payload.
- [x] Slash command request receives immediate success response (avoid Slack timeout).
- [ ] Crew runs successfully after command and posts to Slack.
- [x] Endpoint returns `HTTP 400` for missing/empty ticket input.
- [x] Endpoint returns `HTTP 500` for crew failure.
- [ ] End-to-end test in Slack command verifies threaded or channel response appears.

---

## Phase 4 — Testing + Quality Gate

### Dev 2 (Primary Owner)
- [x] `tests/test_shared.py` covers required env + model defaults.
- [x] `tests/test_leadsync_crew.py` covers happy path + model fallback.
- [x] `tests/test_digest_crew.py` covers happy path + model fallback.
- [x] `tests/test_slack_crew.py` covers parse + happy path + model fallback.
- [x] `tests/test_main.py` covers health + all endpoint success/error paths.
- [x] All tests pass: `pytest -q`.
- [x] Coverage target met: `pytest --cov=src --cov-report=term-missing -q` >= 60%. (actual: 88%)

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
- [ ] Slack slash command `/leadsync` points to `<public-url>/slack/commands`.
- [ ] Slack app/bot has required scopes and channel access.
- [ ] Railway deploy configured with all required env vars.
- [ ] Railway `/health` verified.
- [ ] Jira + Slack integrations switched from ngrok URL to Railway URL when ready.

### Full E2E Demo Checklist
- [ ] Workflow 1 demo: new Jira ticket -> enriched ticket + prompt attachment.
- [ ] Workflow 2 demo: digest trigger -> Slack summary posted.
- [ ] Workflow 3 demo: `/leadsync` question -> reasoned Slack answer posted.
- [ ] Logs are readable and useful during all demo beats.

---

## Phase 6 — Robustness Enhancements (Hackathon Scope)

### Jira History Context (Dev 2)
- [ ] Define same-category ticket selection rule.
- [ ] Retrieve last 5 completed tickets in category.
- [ ] Summarize patterns from completed tickets (approach, pitfalls, constraints).
- [ ] Inject this precedent context into Workflow 3 reasoning prompt.
- [ ] Add/extend tests for this behavior.

### GitHub Intelligence Upgrade (Dev 1 + Dev 2)
- [ ] Define daily analysis trigger approach.
- [ ] Implement scheduled daily repository analysis.
- [ ] Keep on-demand endpoint/command for recent code-change questions.
- [ ] Reuse Workflow 2 primitives where possible.
- [ ] Add tests and failure handling for both scheduled and on-demand paths.

---

## Phase 7 — Tech Lead Preferences System

> **Context:** Fast-pace startup environment where developers change seats/departments frequently.
> The tech lead needs a way to maintain live coding preferences (style, constraints, architectural rules)
> that are automatically injected into AI responses without editing files on disk.

### Dev 1 (Endpoint)
- [x] `POST /slack/prefs` endpoint added to `src/main.py`.
- [x] Handles Slack form-encoded payload (same pattern as `/slack/commands`).
- [x] Handles `ssl_check=1` correctly.
- [x] Parses `add <rule text>` command; returns HTTP 400 for empty or missing text.
- [x] Returns ephemeral Slack response: `"Preference added: {rule_text}"`.
- [ ] Slack slash command `/leadsync-prefs` points to `<public-url>/slack/prefs`.

### Dev 2 (Module + Refactor)
- [x] `src/prefs.py` created with `load_preferences()` and `append_preference(text)`.
- [x] `append_preference()` appends bullet under `## Quick Rules (added via Slack)` section.
- [x] `append_preference()` creates the section if absent.
- [x] `slack_crew.py` refactored: `_load_tech_lead_context()` replaced with `prefs.load_preferences()`.
- [x] `slack_crew.py` classifies Slack question intent as `QUESTION_TYPE: IMPLEMENTATION` or `QUESTION_TYPE: GENERAL`.
- [x] `slack_crew.py` applies preferences only for `IMPLEMENTATION`; `GENERAL` responses stay factual and preference-free.
- [x] `tests/test_prefs.py` covers load, append-existing-section, append-creates-section.
- [x] `tests/test_main.py` extended: prefs endpoint success + 400 + ssl_check cases.
- [x] `tests/test_slack_crew.py` extended for question classification and conditional reason-task branching.

---

## Checkpoint Summary (Mark When Fully Verified)

- [ ] Checkpoint A: Local environment + base integrations verified.
- [ ] Checkpoint B: Workflow 1 production-like behavior verified.
- [ ] Checkpoint C: All 3 workflows execute without exceptions.
- [x] Checkpoint D: Tests green with target coverage. (51 tests passing, 88% coverage)
- [ ] Checkpoint E: Live deploy + external integrations verified.
- [ ] Checkpoint F: Demo rehearsal complete and stable.

---

## Status Log

| Date | Owner | Update |
|------|-------|--------|
| 2026-02-28 | Dev 1 | Added `railway.json` with explicit Railpack start command (`uvicorn src.main:app --host 0.0.0.0 --port $PORT`) and `/health` healthcheck to resolve `railway up` auto-detection failure. |
| 2026-02-28 | Dev 2 | Added minimal backend/frontend/db ruleset template files under `templates/` and improved Workflow 1 ruleset matching to select related rulesets from Jira labels/components; added tests for matching behavior. |
| 2026-02-28 | Dev 2 | Implemented conditional preference injection in Workflow 3 (`QUESTION_TYPE` classification + conditional reasoning branch) and added 2 Slack crew prompt tests; suite now 51 passing tests. |
| 2026-02-28 | Dev 2 | Implemented Workflow 1 deterministic prompt artifact flow: generates `artifacts/workflow1/prompt-[ticket-key].md` with required sections and attaches via `JIRA_ADD_ATTACHMENT`; added tests for section structure and attachment failure handling. |
| 2026-02-28 | Dev 2 | Fixed Workflow 1 Jira attachment bug where filename-only upload failed; now passes absolute path for both `local_file_path` and `file_to_upload`, adds explicit file existence check, and extends test coverage. |
