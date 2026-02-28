# Tech Lead Preferences System — Design

**Date:** 2026-02-27
**Status:** Approved

---

## Problem

The tech lead context file (`config/tech-lead-context.md`) is a static file that requires direct disk access to update. There is no way for a tech lead to add or update preferences from within the tools the team already uses (Slack).

Additionally, `slack_crew.py` has a private `_load_tech_lead_context()` function that duplicates load logic that should be shared.

---

## Goal

Allow a tech lead to append new preferences/rules from Slack via `/leadsync-prefs add "rule text"`, with the change immediately reflected in the next AI response for Workflow 3 (Slack Q&A).

---

## Scope

- **In scope:** Add-only via Slack slash command. Workflow 3 (Slack Q&A) uses preferences. Shared loader module.
- **Out of scope:** Preference versioning, deletion, view command, Workflow 1 injection, authentication/authorization.

---

## Architecture

```
config/
  tech-lead-context.md       ← existing file, unchanged format

src/
  prefs.py                   ← NEW: load_preferences(), append_preference()
  main.py                    ← add POST /slack/prefs endpoint
  slack_crew.py              ← replace _load_tech_lead_context() with prefs.load_preferences()

tests/
  test_prefs.py              ← NEW: unit tests
```

---

## Components

### `src/prefs.py`

Module with two public functions:

```python
def load_preferences() -> str:
    """Read and return config/tech-lead-context.md content."""

def append_preference(text: str) -> None:
    """Append a new bullet under '## Quick Rules (added via Slack)' section.
    Creates the section if absent."""
```

**File mutation behavior:**
- Looks for `## Quick Rules (added via Slack)` sentinel line in the file.
- If found: appends `\n- {text}` after the last item in the section.
- If not found: appends `\n\n## Quick Rules (added via Slack)\n\n- {text}` at end of file.

### `POST /slack/prefs` in `src/main.py`

- Accepts Slack `application/x-www-form-urlencoded` payload.
- Handles `ssl_check=1` the same way `/slack/commands` does.
- Parses `text` field: must start with `add ` followed by non-empty rule text.
- Calls `append_preference(rule_text)`.
- Returns `{"response_type": "ephemeral", "text": "Preference added: {rule_text}"}`.
- Returns HTTP 400 for empty text or missing `add` prefix.

### `slack_crew.py` refactor

Replace private `_load_tech_lead_context()` and the `TECH_LEAD_CONTEXT_PATH` constant with an import of `load_preferences` from `src.prefs`. No behavioral change — identical content loaded.

---

## Data Flow

```
Tech lead types in Slack:
  /leadsync-prefs add "Always wrap DB calls in transactions"

  → Slack POST /slack/prefs (form-encoded)
  → main.py parses text: "add Always wrap DB calls in transactions"
  → prefs.append_preference("Always wrap DB calls in transactions")
  → config/tech-lead-context.md updated on disk
  → returns ephemeral: "Preference added: Always wrap DB calls in transactions"

Next developer question:
  /leadsync LEADS-42 Should I use a raw query here?

  → slack_crew.py calls prefs.load_preferences()
  → preferences file (with new rule) injected into Tech Lead Reasoner prompt
  → AI answer includes the new constraint
```

---

## Test Plan

`tests/test_prefs.py`:
1. `load_preferences()` returns file content from a temp file fixture.
2. `append_preference()` appends correctly formatted bullet to existing file.
3. `append_preference()` creates `## Quick Rules` section when absent.
4. `append_preference()` does not duplicate the section header on second call.

`tests/test_main.py` (additions):
5. `POST /slack/prefs` with `add rule text` → 200 + ephemeral response body.
6. `POST /slack/prefs` with empty text → 400.
7. `POST /slack/prefs` ssl_check → 200 ok.

---

## What This Enables for the Demo

1. Show `config/tech-lead-context.md` in editor — static, existing rules visible.
2. Type `/leadsync-prefs add "Never call sync DB from async handlers"` in Slack.
3. Show the file again — new bullet appears under `## Quick Rules`.
4. Ask a related question via `/leadsync LEADS-X ...` — AI answer cites the new rule.
