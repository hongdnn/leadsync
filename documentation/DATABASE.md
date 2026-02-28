# LeadSync SQLite Database

LeadSync uses a local SQLite database for hybrid memory that persists workflow events, curated insights, and idempotency locks. The memory subsystem is **optional** (disable via `LEADSYNC_MEMORY_ENABLED=false`) and **best-effort** — failures never break workflow execution.

---

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `LEADSYNC_MEMORY_DB_PATH` | `data/leadsync.db` | SQLite file path |
| `LEADSYNC_MEMORY_ENABLED` | `true` | Enable/disable the entire memory subsystem |
| `LEADSYNC_DIGEST_IDEMPOTENCY_ENABLED` | `true` | Enable/disable digest deduplication locks |

---

## Schema

### `events` table

Raw workflow execution records for observability and audit.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment row ID |
| `event_type` | TEXT NOT NULL | Event identifier (e.g. `ticket_enrichment_run`) |
| `workflow` | TEXT NOT NULL | Workflow name (`workflow1`, `workflow2`, etc.) |
| `ticket_key` | TEXT | Jira issue key (nullable) |
| `project_key` | TEXT | Jira project key (nullable) |
| `label` | TEXT | Primary Jira label (nullable) |
| `component` | TEXT | Primary Jira component (nullable) |
| `payload_json` | TEXT NOT NULL | JSON-serialized event data |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC timestamp |

**Indexes:**
- `idx_events_ticket_created` — `(ticket_key, created_at DESC)`
- `idx_events_workflow_created` — `(workflow, created_at DESC)`

### `memory_items` table

Curated, domain-specific records used for context retrieval in agent prompts.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment row ID |
| `workflow` | TEXT NOT NULL | Source workflow |
| `item_type` | TEXT NOT NULL | Semantic type (see Item Types below) |
| `ticket_key` | TEXT | Jira issue key (nullable) |
| `project_key` | TEXT | Jira project key (nullable) |
| `label` | TEXT | Primary label for similarity matching |
| `component` | TEXT | Primary component for similarity matching |
| `repo_key` | TEXT | Repository identifier (nullable) |
| `team_key` | TEXT | Team identifier (nullable) |
| `summary` | TEXT NOT NULL | Human-readable summary |
| `decision` | TEXT | Key decision or insight captured |
| `rules_applied` | TEXT | Which preference category was applied |
| `context_json` | TEXT | JSON-serialized additional context |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC timestamp |

**Indexes:**
- `idx_memory_ticket` — `(ticket_key, created_at DESC)`
- `idx_memory_digest` — `(item_type, created_at DESC)`
- `idx_memory_similarity` — `(label, component, item_type, created_at DESC)`

### `idempotency_locks` table

Prevents duplicate workflow runs (currently used by Workflow 2 digest).

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment row ID |
| `workflow` | TEXT NOT NULL | Workflow name |
| `lock_key` | TEXT NOT NULL | Deterministic key for one logical run |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC timestamp |

**Constraint:** `UNIQUE(workflow, lock_key)`

---

## Item Types

| `item_type` | Written by | Read by | Purpose |
|-------------|-----------|---------|---------|
| `ticket_enrichment` | WF1 | WF3 context query | Ticket enrichment decisions for Q&A context |
| `daily_digest_area` | WF2 | WF3 context query | Recent team activity by code area |
| `slack_qa` | WF3 | WF3 similarity query | Past Q&A for same label/component |
| `leader_rule` | `/slack/prefs` | WF1 + WF3 prompts | Team constraints from tech lead |

## Event Types

| `event_type` | Workflow | Payload fields |
|--------------|----------|----------------|
| `ticket_enrichment_run` | WF1 | `preference_category`, `model`, `prompt_file`, `repo_owner`, `repo_name`, `key_file_count` |
| `github_commit_batch` | WF2 | `scan_summary`, `window_minutes`, `run_source`, `bucket_start_utc` |
| `daily_digest_posted` | WF2 | `digest_summary`, `area_count`, `window_minutes`, `run_source` |
| `slack_question_answered` | WF3 | `question`, `answer`, `thread_ts`, `channel_id` |
| `done_scan_run` | WF6 | Implementation details |

---

## Workflow Usage

### Workflow 1 (Ticket Enrichment)
- **Writes:** `ticket_enrichment_run` event + `ticket_enrichment` memory item
- **Reads:** Leader rules via `query_leader_rules()`

### Workflow 2 (End-of-Day Digest)
- **Writes:** `github_commit_batch` event, `daily_digest_area` memory items, `daily_digest_posted` event
- **Reads:** Idempotency lock via `acquire_idempotency_lock()`

### Workflow 3 (Slack Q&A)
- **Writes:** `slack_question_answered` event + `slack_qa` memory item
- **Reads:** Full context via `query_slack_memory_context()` — ticket memory, digest signals, similar Q&A

### Workflow 6 (Done Ticket Scan)
- **Writes:** `done_scan_run` event

### `/slack/prefs` endpoint
- **Writes:** `leader_rule` memory items

---

## Code Modules

| Module | Exports | Purpose |
|--------|---------|---------|
| `src/memory_store.py` | Facade re-exports | Public API for all workflows |
| `src/memory/schema.py` | `init_memory_db` | Table + index creation (idempotent) |
| `src/memory/write.py` | `record_event`, `record_memory_item`, `acquire_idempotency_lock` | Insert operations |
| `src/memory/query.py` | `query_slack_memory_context`, `query_leader_rules` | Read/query operations |
| `src/memory/types.py` | `MemoryEvent`, `MemoryItem` | Dataclass definitions |

---

## Initialization

Schema is created at FastAPI startup via the `lifespan` hook in `src/main.py`. All `CREATE TABLE` and `CREATE INDEX` statements use `IF NOT EXISTS` for idempotent initialization. Write functions also call `init_memory_db()` before each insert as a safety net.
