"""
tests/test_done_scan_crew.py
Unit tests for Workflow 6: Done Ticket Implementation Scan.
Covers webhook routing, runner, ops, wrapper, and endpoint layers.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.shared import CrewRunResult


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_tool(name: str, run_return=None) -> MagicMock:
    """Build a mock tool with the given name."""
    tool = MagicMock()
    tool.name = name
    if run_return is not None:
        tool.run.return_value = run_return
    return tool


def _done_payload(
    issue_key: str = "LEADS-99",
    summary: str = "Add login page",
    description: str = "Implement the login page UI",
    to_status: str = "Done",
) -> dict:
    """Build a minimal Jira webhook payload for a Done transition."""
    return {
        "issue": {
            "key": issue_key,
            "fields": {
                "summary": summary,
                "description": description,
                "labels": ["backend"],
                "components": [],
                "assignee": {"displayName": "Dev"},
                "project": {"key": "LEADS"},
            },
        },
        "changelog": {
            "items": [
                {
                    "field": "status",
                    "fromString": "In Progress",
                    "toString": to_status,
                }
            ]
        },
    }


def _no_changelog_payload(issue_key: str = "LEADS-99") -> dict:
    """Build a Jira webhook payload without a changelog (e.g. issue created)."""
    return {
        "issue": {
            "key": issue_key,
            "fields": {
                "summary": "New task",
                "description": "Do something",
                "labels": ["frontend"],
                "components": [],
                "assignee": {"displayName": "Dev"},
                "project": {"key": "LEADS"},
            },
        },
    }


def _mock_runtime() -> MagicMock:
    """Build a mock Workflow6Runtime with CrewAI class stubs."""
    runtime = MagicMock()
    runtime.Agent = MagicMock
    runtime.Task = MagicMock
    runtime.Crew = MagicMock
    runtime.Process = MagicMock()
    runtime.Process.sequential = "sequential"
    runtime.memory_enabled.return_value = False
    runtime.build_memory_db_path.return_value = "test.db"
    return runtime


# ── Webhook routing tests ────────────────────────────────────────────────────


class TestIsDoneTransition:

    def test_done_transition_detected(self):
        from src.main import _is_done_transition
        assert _is_done_transition(_done_payload()) is True

    def test_non_done_status_ignored(self):
        from src.main import _is_done_transition
        assert _is_done_transition(_done_payload(to_status="In Review")) is False

    def test_no_changelog_returns_false(self):
        from src.main import _is_done_transition
        assert _is_done_transition(_no_changelog_payload()) is False

    def test_empty_payload_returns_false(self):
        from src.main import _is_done_transition
        assert _is_done_transition({}) is False

    def test_non_dict_changelog_returns_false(self):
        from src.main import _is_done_transition
        assert _is_done_transition({"changelog": "invalid"}) is False

    def test_non_list_items_returns_false(self):
        from src.main import _is_done_transition
        assert _is_done_transition({"changelog": {"items": "invalid"}}) is False

    def test_case_insensitive_done(self):
        from src.main import _is_done_transition
        assert _is_done_transition(_done_payload(to_status="DONE")) is True
        assert _is_done_transition(_done_payload(to_status="done")) is True

    def test_non_status_field_ignored(self):
        from src.main import _is_done_transition
        payload = {
            "changelog": {
                "items": [{"field": "priority", "toString": "Done"}]
            }
        }
        assert _is_done_transition(payload) is False


# ── Runner-layer tests ───────────────────────────────────────────────────────


class TestRunWorkflow6Runner:

    @patch("src.workflow6.runner._required_env", return_value="test-value")
    @patch("src.workflow6.runner.post_done_scan_comment", return_value="posted")
    @patch("src.workflow6.runner.kickoff_with_model_fallback")
    @patch("src.workflow6.runner.build_done_scan_crew")
    def test_happy_path(self, mock_build, mock_kickoff, mock_comment, mock_env):
        from src.workflow6.runner import run_workflow6

        mock_task = MagicMock()
        mock_task.output = MagicMock()
        mock_task.output.raw = "IMPLEMENTATION_SUMMARY: Built login page\nFILES_CHANGED: login.py"
        mock_crew = MagicMock()
        mock_build.return_value = (MagicMock(), mock_task, [MagicMock()], mock_crew)
        mock_kickoff.return_value = ("raw result", "gemini/gemini-2.5-flash")

        runtime = _mock_runtime()
        result = run_workflow6(
            payload=_done_payload(),
            model="gemini/gemini-2.5-flash",
            github_tools=[],
            jira_tools=[],
            runtime=runtime,
        )

        assert isinstance(result, CrewRunResult)
        assert "login" in result.raw.lower()
        assert result.model == "gemini/gemini-2.5-flash"
        mock_comment.assert_called_once()
        mock_build.assert_called_once()

    @patch("src.workflow6.runner._required_env", return_value="test-value")
    @patch("src.workflow6.runner.post_done_scan_comment", return_value="posted")
    @patch("src.workflow6.runner.kickoff_with_model_fallback")
    @patch("src.workflow6.runner.build_done_scan_crew")
    def test_falls_back_to_raw_result_when_no_task_output(
        self, mock_build, mock_kickoff, mock_comment, mock_env
    ):
        from src.workflow6.runner import run_workflow6

        mock_task = MagicMock()
        mock_task.output = None
        mock_crew = MagicMock()
        mock_build.return_value = (MagicMock(), mock_task, [MagicMock()], mock_crew)
        mock_kickoff.return_value = ("fallback raw", "gemini/gemini-2.5-flash")

        runtime = _mock_runtime()
        result = run_workflow6(
            payload=_done_payload(),
            model="gemini/gemini-2.5-flash",
            github_tools=[],
            jira_tools=[],
            runtime=runtime,
        )

        assert result.raw == "fallback raw"

    @patch("src.workflow6.runner._required_env", return_value="test-value")
    @patch("src.workflow6.runner.post_done_scan_comment", return_value="posted")
    @patch("src.workflow6.runner.kickoff_with_model_fallback")
    @patch("src.workflow6.runner.build_done_scan_crew")
    def test_memory_persistence_when_enabled(
        self, mock_build, mock_kickoff, mock_comment, mock_env
    ):
        from src.workflow6.runner import run_workflow6

        mock_task = MagicMock()
        mock_task.output = MagicMock()
        mock_task.output.raw = "summary text"
        mock_build.return_value = (MagicMock(), mock_task, [MagicMock()], MagicMock())
        mock_kickoff.return_value = ("raw", "model")

        runtime = _mock_runtime()
        runtime.memory_enabled.return_value = True

        run_workflow6(
            payload=_done_payload(),
            model="model",
            github_tools=[],
            jira_tools=[],
            runtime=runtime,
        )

        runtime.record_event.assert_called_once()
        call_kwargs = runtime.record_event.call_args.kwargs
        assert call_kwargs["event_type"] == "done_scan_completed"
        assert call_kwargs["workflow"] == "workflow6"

    @patch("src.workflow6.runner._required_env", return_value="test-value")
    @patch("src.workflow6.runner.post_done_scan_comment", return_value="posted")
    @patch("src.workflow6.runner.kickoff_with_model_fallback")
    @patch("src.workflow6.runner.build_done_scan_crew")
    def test_memory_failure_does_not_crash(
        self, mock_build, mock_kickoff, mock_comment, mock_env
    ):
        from src.workflow6.runner import run_workflow6

        mock_task = MagicMock()
        mock_task.output = MagicMock()
        mock_task.output.raw = "summary"
        mock_build.return_value = (MagicMock(), mock_task, [MagicMock()], MagicMock())
        mock_kickoff.return_value = ("raw", "model")

        runtime = _mock_runtime()
        runtime.memory_enabled.return_value = True
        runtime.record_event.side_effect = Exception("db error")

        result = run_workflow6(
            payload=_done_payload(),
            model="model",
            github_tools=[],
            jira_tools=[],
            runtime=runtime,
        )

        assert isinstance(result, CrewRunResult)


# ── Ops-layer tests ──────────────────────────────────────────────────────────


class TestPostDoneScanComment:

    def test_posts_when_no_duplicate(self):
        from src.workflow6.ops import post_done_scan_comment

        get_tool = _make_tool("JIRA_GET_ISSUE", run_return={"fields": {}})
        comment_tool = _make_tool("JIRA_ADD_COMMENT", run_return={"successful": True})
        result = post_done_scan_comment(
            jira_tools=[get_tool, comment_tool],
            issue_key="LEADS-10",
            summary_text="Built the login page.",
        )
        assert result == "posted"
        comment_tool.run.assert_called_once()

    def test_skips_when_duplicate(self):
        from src.workflow6.ops import post_done_scan_comment, JIRA_COMMENT_MARKER

        existing = f"Previous comments... {JIRA_COMMENT_MARKER} Implementation scan..."
        get_tool = _make_tool("JIRA_GET_ISSUE", run_return=existing)
        comment_tool = _make_tool("JIRA_ADD_COMMENT")
        result = post_done_scan_comment(
            jira_tools=[get_tool, comment_tool],
            issue_key="LEADS-10",
            summary_text="Built the login page.",
        )
        assert result == "skipped:duplicate"
        comment_tool.run.assert_not_called()

    def test_skips_when_no_tool(self):
        from src.workflow6.ops import post_done_scan_comment

        result = post_done_scan_comment(
            jira_tools=[],
            issue_key="LEADS-10",
            summary_text="Built the login page.",
        )
        assert result == "skipped:no-tool"

    def test_raises_on_tool_failure(self):
        from src.workflow6.ops import post_done_scan_comment

        get_tool = _make_tool("JIRA_GET_ISSUE", run_return={"fields": {}})
        comment_tool = _make_tool(
            "JIRA_ADD_COMMENT",
            run_return={"successful": False, "error": "forbidden"},
        )
        with pytest.raises(RuntimeError, match="JIRA_ADD_COMMENT failed"):
            post_done_scan_comment(
                jira_tools=[get_tool, comment_tool],
                issue_key="LEADS-10",
                summary_text="Built the login page.",
            )

    def test_proceeds_when_get_issue_fails(self):
        from src.workflow6.ops import post_done_scan_comment

        get_tool = _make_tool("JIRA_GET_ISSUE")
        get_tool.run.side_effect = Exception("api error")
        comment_tool = _make_tool("JIRA_ADD_COMMENT", run_return={"successful": True})
        result = post_done_scan_comment(
            jira_tools=[get_tool, comment_tool],
            issue_key="LEADS-10",
            summary_text="Built the login page.",
        )
        assert result == "posted"


# ── Wrapper-layer tests ──────────────────────────────────────────────────────


class TestRunDoneScanCrew:

    @patch("src.done_scan_crew.run_workflow6")
    @patch("src.done_scan_crew.build_tools", return_value=[])
    @patch("src.done_scan_crew.composio_user_id", return_value="default")
    @patch("src.done_scan_crew.build_llm", return_value="gemini/gemini-2.5-flash")
    def test_builds_tools_and_calls_runner(
        self, mock_llm, mock_uid, mock_build, mock_run
    ):
        mock_run.return_value = CrewRunResult(
            raw="IMPLEMENTATION_SUMMARY: done", model="gemini/gemini-2.5-flash"
        )
        from src.done_scan_crew import run_done_scan_crew

        result = run_done_scan_crew(payload=_done_payload())
        assert isinstance(result, CrewRunResult)
        assert "done" in result.raw.lower()
        mock_run.assert_called_once()

    @patch("src.done_scan_crew.run_workflow6")
    @patch("src.done_scan_crew.build_tools", return_value=[])
    @patch("src.done_scan_crew.composio_user_id", return_value="test-user-42")
    @patch("src.done_scan_crew.build_llm", return_value="gemini/gemini-2.5-flash")
    def test_uses_composio_user_id(self, mock_llm, mock_uid, mock_build, mock_run):
        mock_run.return_value = CrewRunResult(raw="ok", model="model")
        from src.done_scan_crew import run_done_scan_crew

        run_done_scan_crew(payload=_done_payload())
        calls = mock_build.call_args_list
        for call in calls:
            assert call.kwargs["user_id"] == "test-user-42"

    @patch("src.done_scan_crew.run_workflow6")
    @patch("src.done_scan_crew.build_tools", return_value=[])
    @patch("src.done_scan_crew.composio_user_id", return_value="default")
    @patch("src.done_scan_crew.build_llm", return_value="gemini/gemini-2.5-flash")
    def test_requests_correct_jira_tools(
        self, mock_llm, mock_uid, mock_build, mock_run
    ):
        mock_run.return_value = CrewRunResult(raw="ok", model="model")
        from src.done_scan_crew import run_done_scan_crew

        run_done_scan_crew(payload=_done_payload())
        jira_call = [
            c for c in mock_build.call_args_list
            if c.kwargs.get("tools") and any(t.startswith("JIRA_") for t in c.kwargs["tools"])
        ]
        assert len(jira_call) == 1
        assert "JIRA_GET_ISSUE" in jira_call[0].kwargs["tools"]
        assert "JIRA_ADD_COMMENT" in jira_call[0].kwargs["tools"]


# ── Endpoint-layer tests ─────────────────────────────────────────────────────


class TestJiraWebhookWf6Integration:

    @pytest.fixture
    def client(self):
        from src.main import app
        from fastapi.testclient import TestClient

        return TestClient(app)

    @patch("src.main.run_done_scan_crew")
    @patch("src.main.run_leadsync_crew")
    def test_done_transition_routes_to_wf6(self, mock_wf1, mock_wf6, client):
        mock_wf6.return_value = CrewRunResult(
            raw="scanned implementation", model="gemini/gemini-2.5-flash"
        )
        response = client.post("/webhooks/jira", json=_done_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "scanned implementation"
        mock_wf6.assert_called_once()
        mock_wf1.assert_not_called()

    @patch("src.main.run_done_scan_crew")
    @patch("src.main.run_leadsync_crew")
    def test_non_done_transition_routes_to_wf1(self, mock_wf1, mock_wf6, client):
        mock_wf1.return_value = CrewRunResult(
            raw="enriched ticket", model="gemini/gemini-2.5-flash"
        )
        response = client.post("/webhooks/jira", json=_no_changelog_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "enriched ticket"
        mock_wf1.assert_called_once()
        mock_wf6.assert_not_called()

    @patch("src.main.run_done_scan_crew")
    @patch("src.main.run_leadsync_crew")
    def test_in_progress_transition_routes_to_wf1(self, mock_wf1, mock_wf6, client):
        mock_wf1.return_value = CrewRunResult(raw="enriched", model="model")
        payload = _done_payload(to_status="In Progress")
        response = client.post("/webhooks/jira", json=payload)
        assert response.status_code == 200
        mock_wf1.assert_called_once()
        mock_wf6.assert_not_called()

    @patch("src.main.run_done_scan_crew", side_effect=RuntimeError("missing env"))
    def test_wf6_runtime_error_returns_400(self, mock_wf6, client):
        response = client.post("/webhooks/jira", json=_done_payload())
        assert response.status_code == 400
        assert "missing env" in response.json()["detail"]

    @patch("src.main.run_done_scan_crew", side_effect=Exception("crew boom"))
    def test_wf6_generic_error_returns_500(self, mock_wf6, client):
        response = client.post("/webhooks/jira", json=_done_payload())
        assert response.status_code == 500
        assert "Crew run failed" in response.json()["detail"]
