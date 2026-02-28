# Conditional Preference Injection — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Inject tech lead preferences into Slack Q&A responses only when the developer's question asks HOW to implement something; return pure Jira facts for general questions.

**Architecture:** Modify `retrieve_task` description in `slack_crew.py` to include a classification step (QUESTION_TYPE: IMPLEMENTATION or GENERAL). Modify `reason_task` description to branch on that flag — applying preferences only for IMPLEMENTATION questions, returning factual ticket info for GENERAL ones. No new files, no new agents, no Python logic changes — purely prompt engineering.

**Tech Stack:** CrewAI Task descriptions · pytest + unittest.mock

---

## Context: What the current code looks like

`src/slack_crew.py` lines 92–112 (the two task descriptions being changed):

```python
retrieve_task = Task(
    description=(
        f"Fetch Jira ticket {ticket_key}.\n"
        "- Include summary, description, labels, assignee, and comments.\n"
        f"- Developer question: {question}"
    ),
    expected_output="Structured Jira ticket context for downstream reasoning.",
    agent=retriever,
)
reason_task = Task(
    description=(
        "Use the ticket context and this tech lead guidance:\n"
        f"---\n{tech_lead_context}\n---\n"
        f"Question: {question}\n"
        "- Return a direct recommendation in 2-4 sentences.\n"
        "- Mention tradeoffs when they matter."
    ),
    expected_output="Opinionated answer that references relevant project constraints.",
    agent=reasoner,
    context=[retrieve_task],
)
```

The test file `tests/test_slack_crew.py` patches `src.slack_crew.Task` — so `mock_task_cls.call_args_list[0]` is the retrieve_task call and `mock_task_cls.call_args_list[1]` is the reason_task call. Access the `description` kwarg to inspect prompt content.

---

## Task 1: Update task descriptions in `src/slack_crew.py`

**Files:**
- Modify: `src/slack_crew.py:92-112`
- Test: `tests/test_slack_crew.py`

---

### Step 1: Write two failing tests that inspect Task description content

Append these two tests to the end of `tests/test_slack_crew.py`:

```python
@patch("src.slack_crew.Task")
@patch("src.slack_crew.Agent")
@patch("src.slack_crew.build_tools")
@patch("src.slack_crew.build_llm")
@patch("src.slack_crew.Crew")
def test_retrieve_task_contains_classification_instructions(
    mock_crew_cls, mock_build_llm, mock_build_tools, mock_agent_cls, mock_task_cls,
    monkeypatch,
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    mock_build_llm.return_value = "gemini/gemini-2.5-flash"
    mock_build_tools.return_value = []
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock(__str__=lambda s: "done")
    mock_crew_cls.return_value = mock_crew_instance

    with patch("src.slack_crew.load_preferences", return_value="# Prefs"):
        from src.slack_crew import run_slack_crew
        run_slack_crew(ticket_key="LEADS-1", question="How should I implement this?")

    retrieve_call = mock_task_cls.call_args_list[0]
    desc = retrieve_call[1]["description"]
    assert "QUESTION_TYPE" in desc
    assert "IMPLEMENTATION" in desc
    assert "GENERAL" in desc


@patch("src.slack_crew.Task")
@patch("src.slack_crew.Agent")
@patch("src.slack_crew.build_tools")
@patch("src.slack_crew.build_llm")
@patch("src.slack_crew.Crew")
def test_reason_task_contains_conditional_branches(
    mock_crew_cls, mock_build_llm, mock_build_tools, mock_agent_cls, mock_task_cls,
    monkeypatch,
):
    monkeypatch.setenv("COMPOSIO_USER_ID", "default")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C12345")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    mock_build_llm.return_value = "gemini/gemini-2.5-flash"
    mock_build_tools.return_value = []
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = MagicMock(__str__=lambda s: "done")
    mock_crew_cls.return_value = mock_crew_instance

    with patch("src.slack_crew.load_preferences", return_value="# Prefs\n- Prefer async."):
        from src.slack_crew import run_slack_crew
        run_slack_crew(ticket_key="LEADS-1", question="Should I use a new table?")

    reason_call = mock_task_cls.call_args_list[1]
    desc = reason_call[1]["description"]
    assert "QUESTION_TYPE: GENERAL" in desc
    assert "QUESTION_TYPE: IMPLEMENTATION" in desc
    assert "Do NOT reference or apply any tech lead preferences" in desc
    assert "Prefer async" in desc  # preferences are still passed in; agent decides when to use them
```

### Step 2: Run to confirm they fail

```
pytest tests/test_slack_crew.py::test_retrieve_task_contains_classification_instructions tests/test_slack_crew.py::test_reason_task_contains_conditional_branches -v
```

Expected: both FAIL — current task descriptions don't contain `QUESTION_TYPE`, classification rules, or conditional branches.

### Step 3: Replace the two task descriptions in `src/slack_crew.py`

Find and replace the `retrieve_task` block (lines 92–100):

**Replace:**
```python
    retrieve_task = Task(
        description=(
            f"Fetch Jira ticket {ticket_key}.\n"
            "- Include summary, description, labels, assignee, and comments.\n"
            f"- Developer question: {question}"
        ),
        expected_output="Structured Jira ticket context for downstream reasoning.",
        agent=retriever,
    )
```

**With:**
```python
    retrieve_task = Task(
        description=(
            f"Fetch Jira ticket {ticket_key}.\n"
            "- Include summary, description, labels, assignee, and comments.\n"
            f"- Developer question: {question}\n"
            "After fetching the ticket, classify the developer question using this rule:\n"
            "  IMPLEMENTATION: asks HOW to do something, WHICH approach to take, "
            "SHOULD I use X or Y, HOW TO structure or design something.\n"
            "  GENERAL: asks WHAT the ticket is about, WHO is assigned, WHEN it is due, "
            "status, description, or acceptance criteria.\n"
            "Output the classification as the FIRST line of your response in this exact format:\n"
            "QUESTION_TYPE: IMPLEMENTATION\n"
            "or\n"
            "QUESTION_TYPE: GENERAL"
        ),
        expected_output="QUESTION_TYPE label on the first line, followed by structured Jira ticket context.",
        agent=retriever,
    )
```

Find and replace the `reason_task` block (lines 101–112):

**Replace:**
```python
    reason_task = Task(
        description=(
            "Use the ticket context and this tech lead guidance:\n"
            f"---\n{tech_lead_context}\n---\n"
            f"Question: {question}\n"
            "- Return a direct recommendation in 2-4 sentences.\n"
            "- Mention tradeoffs when they matter."
        ),
        expected_output="Opinionated answer that references relevant project constraints.",
        agent=reasoner,
        context=[retrieve_task],
    )
```

**With:**
```python
    reason_task = Task(
        description=(
            f"Question: {question}\n\n"
            "Read the QUESTION_TYPE from the retriever output and follow the matching branch:\n\n"
            "If QUESTION_TYPE: GENERAL\n"
            "- Return only factual information from the ticket in 1-2 sentences.\n"
            "- Do NOT reference or apply any tech lead preferences.\n"
            "- Do NOT give implementation opinions.\n\n"
            "If QUESTION_TYPE: IMPLEMENTATION\n"
            "- Apply the following tech lead guidance to give an opinionated recommendation:\n"
            f"---\n{tech_lead_context}\n---\n"
            "- Return a direct recommendation in 2-4 sentences.\n"
            "- Mention tradeoffs when they matter."
        ),
        expected_output=(
            "Either a factual 1-2 sentence answer (GENERAL) or an opinionated "
            "recommendation citing relevant project constraints (IMPLEMENTATION)."
        ),
        agent=reasoner,
        context=[retrieve_task],
    )
```

### Step 4: Run all tests to confirm everything passes

```
pytest tests/ -v
```

Expected: all 51 tests PASS (49 existing + 2 new).

### Step 5: Commit

```
git add src/slack_crew.py tests/test_slack_crew.py
git commit -m "feat: conditionally inject tech lead preferences based on question intent"
```

---

## Task 2: Push to remote

### Step 1: Push

```
git push origin main
```

Expected: push succeeds.

### Step 2: Verify

```
git log --oneline origin/main..HEAD
```

Expected: empty (all commits pushed).
