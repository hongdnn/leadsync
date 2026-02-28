# Tech Lead Preferences System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow a tech lead to append new preference rules from Slack via `/leadsync-prefs add "rule"`, with the rule immediately reflected in Workflow 3 (Slack Q&A) AI responses.

**Architecture:** New `src/prefs.py` module with `load_preferences()` (shared file reader) and `append_preference(text)` (appends bullet to a dedicated section in `config/tech-lead-context.md`). New `POST /slack/prefs` endpoint parses the Slack slash command and calls `append_preference()`. `slack_crew.py` is refactored to import `load_preferences` from `prefs` instead of using its private loader.

**Tech Stack:** FastAPI · Python pathlib · pytest + unittest.mock

---

## Task 1: Create `src/prefs.py` with tests

**Files:**
- Create: `src/prefs.py`
- Create: `tests/test_prefs.py`

---

### Step 1: Write the failing tests

Create `tests/test_prefs.py`:

```python
"""
tests/test_prefs.py
Unit tests for src/prefs.py — tech lead preferences loader and appender.
"""

from pathlib import Path
import pytest


def test_load_preferences_returns_file_content(tmp_path):
    prefs_file = tmp_path / "tech-lead-context.md"
    prefs_file.write_text("# Preferences\n- Prefer async.")
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "src.prefs.TECH_LEAD_CONTEXT_PATH", prefs_file
    ):
        from src.prefs import load_preferences
        result = load_preferences()
    assert "Prefer async" in result


def test_append_preference_creates_section_when_absent(tmp_path):
    prefs_file = tmp_path / "tech-lead-context.md"
    prefs_file.write_text("# Existing Content\n- Some rule.\n")
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "src.prefs.TECH_LEAD_CONTEXT_PATH", prefs_file
    ):
        from src.prefs import append_preference
        append_preference("Always wrap DB calls in transactions")
    content = prefs_file.read_text()
    assert "## Quick Rules (added via Slack)" in content
    assert "Always wrap DB calls in transactions" in content


def test_append_preference_adds_to_existing_section(tmp_path):
    prefs_file = tmp_path / "tech-lead-context.md"
    prefs_file.write_text(
        "# Existing Content\n\n## Quick Rules (added via Slack)\n\n- First rule.\n"
    )
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "src.prefs.TECH_LEAD_CONTEXT_PATH", prefs_file
    ):
        from src.prefs import append_preference
        append_preference("Second rule here")
    content = prefs_file.read_text()
    assert content.count("## Quick Rules (added via Slack)") == 1
    assert "Second rule here" in content


def test_append_preference_does_not_duplicate_section_header(tmp_path):
    prefs_file = tmp_path / "tech-lead-context.md"
    prefs_file.write_text(
        "## Quick Rules (added via Slack)\n\n- Rule one.\n"
    )
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "src.prefs.TECH_LEAD_CONTEXT_PATH", prefs_file
    ):
        from src.prefs import append_preference
        append_preference("Rule two")
        append_preference("Rule three")
    content = prefs_file.read_text()
    assert content.count("## Quick Rules (added via Slack)") == 1
    assert "Rule two" in content
    assert "Rule three" in content
```

### Step 2: Run tests to confirm they fail

```
venv\Scripts\activate && pytest tests/test_prefs.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `src.prefs` does not exist yet.

### Step 3: Implement `src/prefs.py`

```python
"""
src/prefs.py
Tech lead preferences loader and updater.
Exports: load_preferences, append_preference
"""

from pathlib import Path

TECH_LEAD_CONTEXT_PATH = Path(__file__).parent.parent / "config" / "tech-lead-context.md"
_QUICK_RULES_HEADER = "## Quick Rules (added via Slack)"


def load_preferences() -> str:
    """
    Read and return the tech lead context file.

    Returns:
        Full markdown content of config/tech-lead-context.md.
    Side effects:
        Reads from filesystem.
    """
    return TECH_LEAD_CONTEXT_PATH.read_text(encoding="utf-8")


def append_preference(text: str) -> None:
    """
    Append a new rule bullet to the Quick Rules section of the preferences file.

    Creates the section at end of file if it does not exist.
    If the section already exists, appends after the last bullet.

    Args:
        text: Plain-text rule to append (no leading dash needed).
    Side effects:
        Writes to config/tech-lead-context.md on disk.
    """
    content = TECH_LEAD_CONTEXT_PATH.read_text(encoding="utf-8")
    new_bullet = f"- {text}"
    if _QUICK_RULES_HEADER in content:
        content = content.rstrip("\n") + f"\n{new_bullet}\n"
    else:
        content = content.rstrip("\n") + f"\n\n{_QUICK_RULES_HEADER}\n\n{new_bullet}\n"
    TECH_LEAD_CONTEXT_PATH.write_text(content, encoding="utf-8")
```

### Step 4: Run tests to confirm they pass

```
venv\Scripts\activate && pytest tests/test_prefs.py -v
```

Expected: all 4 tests PASS.

### Step 5: Commit

```
git add src/prefs.py tests/test_prefs.py
git commit -m "feat: add prefs module with load_preferences and append_preference"
```

---

## Task 2: Add `POST /slack/prefs` endpoint

**Files:**
- Modify: `src/main.py` (add import + new endpoint)
- Modify: `tests/test_main.py` (add 3 new tests)

---

### Step 1: Write failing tests

Append these tests to `tests/test_main.py`:

```python
# ── /slack/prefs endpoint ───────────────────────────────────────────────────

@patch("src.main.append_preference")
def test_slack_prefs_add_success(mock_append, client):
    response = client.post(
        "/slack/prefs",
        content=b"text=add+Always+use+async",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["response_type"] == "ephemeral"
    assert "Always use async" in data["text"]
    mock_append.assert_called_once_with("Always use async")


@patch("src.main.append_preference")
def test_slack_prefs_empty_text_returns_400(mock_append, client):
    response = client.post(
        "/slack/prefs",
        content=b"text=",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400
    mock_append.assert_not_called()


@patch("src.main.append_preference")
def test_slack_prefs_ssl_check_returns_ok(mock_append, client):
    response = client.post(
        "/slack/prefs",
        content=b"ssl_check=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_append.assert_not_called()
```

### Step 2: Run tests to confirm they fail

```
venv\Scripts\activate && pytest tests/test_main.py::test_slack_prefs_add_success tests/test_main.py::test_slack_prefs_empty_text_returns_400 tests/test_main.py::test_slack_prefs_ssl_check_returns_ok -v
```

Expected: FAIL — endpoint does not exist.

### Step 3: Add import and endpoint to `src/main.py`

At the top of `src/main.py`, add to the imports:

```python
from src.prefs import append_preference
```

Add this endpoint after the `slack_command` function (before `_run_slack_crew_background`):

```python
@app.post("/slack/prefs")
async def slack_prefs(request: Request) -> dict[str, str]:
    """
    Handle /leadsync-prefs Slack slash command to append tech lead preferences.

    Accepts Slack application/x-www-form-urlencoded payload.
    Supported command: add <rule text>

    Args:
        request: FastAPI Request for content-type handling.
    Returns:
        Ephemeral Slack response confirming the preference was added.
    Raises:
        HTTPException 400: If text is empty or command is not 'add'.
    """
    raw_body = await request.body()
    form_data = parse_qs(raw_body.decode("utf-8"))

    if form_data.get("ssl_check", [""])[0].strip() == "1":
        return {"status": "ok"}

    text = form_data.get("text", [""])[0].strip()
    if not text:
        raise HTTPException(status_code=400, detail="Slack 'text' field is empty.")

    if not text.lower().startswith("add "):
        raise HTTPException(
            status_code=400,
            detail="Unknown command. Usage: /leadsync-prefs add <rule text>",
        )

    rule_text = text[4:].strip()
    if not rule_text:
        raise HTTPException(status_code=400, detail="Rule text cannot be empty.")

    append_preference(rule_text)
    return {
        "response_type": "ephemeral",
        "text": f"Preference added: {rule_text}",
    }
```

### Step 4: Run tests to confirm they pass

```
venv\Scripts\activate && pytest tests/test_main.py -v
```

Expected: all tests including the 3 new ones PASS.

### Step 5: Commit

```
git add src/main.py tests/test_main.py
git commit -m "feat: add POST /slack/prefs endpoint for tech lead preference updates"
```

---

## Task 3: Refactor `slack_crew.py` to use shared `load_preferences`

**Files:**
- Modify: `src/slack_crew.py` (replace private loader with `prefs.load_preferences`)
- Modify: `tests/test_slack_crew.py` (update patches to target `src.slack_crew.load_preferences`)

---

### Step 1: Update the tests first

In `tests/test_slack_crew.py`, the existing tests patch `src.slack_crew.TECH_LEAD_CONTEXT_PATH`. After the refactor, `slack_crew.py` will import and call `load_preferences` from `prefs`. We patch the name as it appears in `slack_crew`'s namespace.

Replace every occurrence of:
```python
with patch("src.slack_crew.TECH_LEAD_CONTEXT_PATH", ctx_file):
```

With:
```python
with patch("src.slack_crew.load_preferences", return_value="# Tech Lead Context\nPrefer async."):
```

Also remove the `ctx_file = tmp_path / "tech-lead-context.md"` / `ctx_file.write_text(...)` lines from those tests (no longer needed). Remove `tmp_path` from function signatures where it's no longer used.

The three affected tests are:
- `test_run_slack_crew_returns_crew_run_result`
- `test_run_slack_crew_model_fallback`
- `test_run_slack_crew_raises_on_missing_slack_channel`

### Step 2: Run tests to confirm they still pass before the implementation change

```
venv\Scripts\activate && pytest tests/test_slack_crew.py -v
```

> Note: The tests will still pass because the patch target (`src.slack_crew.TECH_LEAD_CONTEXT_PATH`) still exists in `slack_crew.py` at this point. This verifies the test logic before the refactor.

Actually — at this point `src.slack_crew.load_preferences` does NOT exist yet, so the updated tests will fail. That's fine — we're writing failing tests first (TDD).

Expected: FAIL — `load_preferences` not found in `slack_crew` namespace.

### Step 3: Refactor `src/slack_crew.py`

**Remove** these lines from `slack_crew.py`:
```python
from pathlib import Path
# ...
TECH_LEAD_CONTEXT_PATH = Path(__file__).parent.parent / "config" / "tech-lead-context.md"
```

```python
def _load_tech_lead_context() -> str:
    """
    Load the tech lead guidance file.

    Returns:
        Markdown content from config/tech-lead-context.md.
    Side effects:
        Reads from filesystem.
    """
    return TECH_LEAD_CONTEXT_PATH.read_text(encoding="utf-8")
```

**Add** this import (alongside the existing `src.shared` import):
```python
from src.prefs import load_preferences
```

**Replace** this line inside `run_slack_crew()`:
```python
tech_lead_context = _load_tech_lead_context()
```
With:
```python
tech_lead_context = load_preferences()
```

If `Path` is no longer imported anywhere else in the file, remove it from the `from pathlib import Path` line.

### Step 4: Run all tests to confirm nothing broke

```
venv\Scripts\activate && pytest tests/ -v
```

Expected: all tests PASS.

### Step 5: Commit

```
git add src/slack_crew.py tests/test_slack_crew.py
git commit -m "refactor: slack_crew uses shared prefs.load_preferences instead of private loader"
```

---

## Task 4: Verify full coverage and run all tests

### Step 1: Run tests with coverage report

```
venv\Scripts\activate && pytest --cov=src --cov-report=term-missing -q
```

Expected: coverage >= 60%. `src/prefs.py` should show near 100% coverage.

### Step 2: Final commit if any coverage fixes needed

If any lines are uncovered and can be covered cheaply (no extra logic needed), add a targeted test. Otherwise, leave it — YAGNI.

---

## Demo Script for This Feature

1. Open `config/tech-lead-context.md` in editor — show existing rules.
2. Type in Slack: `/leadsync-prefs add "Never call sync DB from async handlers"`
3. Slack responds: _"Preference added: Never call sync DB from async handlers"_
4. Refresh the file in editor — new bullet appears under `## Quick Rules (added via Slack)`.
5. Ask: `/leadsync LEADS-X Should I use a synchronous query here?`
6. AI response references the just-added constraint — no restart, no re-deploy.
