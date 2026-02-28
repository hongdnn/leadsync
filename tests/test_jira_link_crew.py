"""
tests/test_jira_link_crew.py
Unit tests for Workflow 5: Jira-GitHub PR Auto-Link.
Covers runner, ops, wrapper, and endpoint layers.
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


def _pr_payload(
    action: str = "opened",
    number: int = 42,
    title: str = "LEADS-99: add login",
    body: str = "",
    branch: str = "feature/LEADS-99",
    owner: str = "org",
    repo: str = "repo",
) -> dict:
    """Build a minimal GitHub PR webhook payload."""
    return {
        "action": action,
        "pull_request": {
            "number": number,
            "title": title,
            "body": body,
            "html_url": f"https://github.com/{owner}/{repo}/pull/{number}",
            "head": {"ref": branch, "sha": "abc123"},
            "base": {"sha": "def456"},
        },
        "repository": {
            "name": repo,
            "owner": {"login": owner},
        },
    }


# ── Runner-layer tests ──────────────────────────────────────────────────────

class TestRunWorkflow5Runner:

    @patch("src.workflow5.runner.post_github_no_ticket_warning", return_value="posted")
    @patch("src.workflow5.runner.transition_jira_to_in_review", return_value="transitioned:In Review")
    @patch("src.workflow5.runner.post_jira_pr_link_comment", return_value="posted")
    def test_skips_unsupported_action(self, mock_comment, mock_transition, mock_warning):
        from src.workflow5.runner import run_workflow5
        result = run_workflow5(
            payload=_pr_payload(action="closed"),
            github_tools=[],
            jira_tools=[],
        )
        assert result.raw.startswith("skipped: action")
        mock_comment.assert_not_called()
        mock_transition.assert_not_called()
        mock_warning.assert_not_called()

    @patch("src.workflow5.runner.post_github_no_ticket_warning", return_value="posted")
    @patch("src.workflow5.runner.transition_jira_to_in_review", return_value="transitioned:In Review")
    @patch("src.workflow5.runner.post_jira_pr_link_comment", return_value="posted")
    def test_skips_missing_pr_metadata(self, mock_comment, mock_transition, mock_warning):
        from src.workflow5.runner import run_workflow5
        result = run_workflow5(
            payload=_pr_payload(number=0),
            github_tools=[],
            jira_tools=[],
        )
        assert result.raw == "skipped: missing PR metadata"

    @patch("src.workflow5.runner.post_github_no_ticket_warning", return_value="posted")
    @patch("src.workflow5.runner.transition_jira_to_in_review", return_value="transitioned:In Review")
    @patch("src.workflow5.runner.post_jira_pr_link_comment", return_value="posted")
    def test_linked_when_jira_key_found(self, mock_comment, mock_transition, mock_warning):
        from src.workflow5.runner import run_workflow5
        result = run_workflow5(
            payload=_pr_payload(title="LEADS-42: fix bug", branch="feature/LEADS-42"),
            github_tools=[],
            jira_tools=[],
        )
        assert "linked" in result.raw
        assert "LEADS-42" in result.raw
        mock_comment.assert_called_once()
        mock_transition.assert_called_once()
        mock_warning.assert_not_called()

    @patch("src.workflow5.runner.post_github_no_ticket_warning", return_value="posted")
    @patch("src.workflow5.runner.transition_jira_to_in_review", return_value="transitioned:In Review")
    @patch("src.workflow5.runner.post_jira_pr_link_comment", return_value="posted")
    def test_warned_when_no_jira_key(self, mock_comment, mock_transition, mock_warning):
        from src.workflow5.runner import run_workflow5
        result = run_workflow5(
            payload=_pr_payload(title="fix typo", branch="fix/typo"),
            github_tools=[],
            jira_tools=[],
        )
        assert "warned" in result.raw
        mock_warning.assert_called_once()
        mock_comment.assert_not_called()
        mock_transition.assert_not_called()

    @patch("src.workflow5.runner.post_github_no_ticket_warning", return_value="posted")
    @patch("src.workflow5.runner.transition_jira_to_in_review", return_value="transitioned:In Review")
    @patch("src.workflow5.runner.post_jira_pr_link_comment", return_value="posted")
    def test_returns_rule_engine_model(self, mock_comment, mock_transition, mock_warning):
        from src.workflow5.runner import run_workflow5
        result = run_workflow5(
            payload=_pr_payload(),
            github_tools=[],
            jira_tools=[],
        )
        assert result.model == "rule-engine"


# ── Ops-layer tests ─────────────────────────────────────────────────────────

class TestPostJiraPrLinkComment:

    PR_KWARGS = dict(
        ticket_key="LEADS-10",
        pr_url="https://github.com/org/repo/pull/5",
        pr_number=5,
        pr_title="LEADS-10: add login",
        branch="feature/LEADS-10",
        owner="org",
        repo="repo",
        head_sha="abc1234def5678",
    )

    def test_posts_when_no_duplicate(self):
        from src.workflow5.ops import post_jira_pr_link_comment
        get_tool = _make_tool("JIRA_GET_ISSUE", run_return={"fields": {"comment": {"comments": []}}})
        comment_tool = _make_tool("JIRA_ADD_COMMENT", run_return={"successful": True})
        result = post_jira_pr_link_comment(
            jira_tools=[get_tool, comment_tool],
            **self.PR_KWARGS,
        )
        assert result == "posted"
        comment_tool.run.assert_called_once()

    def test_skips_when_duplicate(self):
        from src.workflow5.ops import post_jira_pr_link_comment, JIRA_COMMENT_MARKER
        existing = f"Previous comments... {JIRA_COMMENT_MARKER} PR linked: https://github.com/org/repo/pull/5"
        get_tool = _make_tool("JIRA_GET_ISSUE", run_return=existing)
        comment_tool = _make_tool("JIRA_ADD_COMMENT")
        result = post_jira_pr_link_comment(
            jira_tools=[get_tool, comment_tool],
            **self.PR_KWARGS,
        )
        assert result == "skipped:duplicate"
        comment_tool.run.assert_not_called()

    def test_skips_when_no_tool(self):
        from src.workflow5.ops import post_jira_pr_link_comment
        result = post_jira_pr_link_comment(
            jira_tools=[],
            **self.PR_KWARGS,
        )
        assert result == "skipped:no-tool"

    def test_raises_on_tool_failure(self):
        from src.workflow5.ops import post_jira_pr_link_comment
        get_tool = _make_tool("JIRA_GET_ISSUE", run_return={"fields": {}})
        comment_tool = _make_tool("JIRA_ADD_COMMENT", run_return={"successful": False, "error": "forbidden"})
        with pytest.raises(RuntimeError, match="JIRA_ADD_COMMENT failed"):
            post_jira_pr_link_comment(
                jira_tools=[get_tool, comment_tool],
                **self.PR_KWARGS,
            )

    def test_comment_body_includes_pr_details(self):
        from src.workflow5.ops import post_jira_pr_link_comment, JIRA_COMMENT_MARKER
        get_tool = _make_tool("JIRA_GET_ISSUE", run_return={"fields": {}})
        comment_tool = _make_tool("JIRA_ADD_COMMENT", run_return={"successful": True})
        post_jira_pr_link_comment(
            jira_tools=[get_tool, comment_tool],
            **self.PR_KWARGS,
        )
        body = comment_tool.run.call_args.kwargs["comment"]
        assert JIRA_COMMENT_MARKER in body
        assert "LEADS-10: add login" in body
        assert "feature/LEADS-10" in body
        assert "org/repo" in body
        assert "abc1234" in body
        assert "Automatically linked by LeadSync" in body


class TestTransitionJiraToInReview:

    def test_transitions_correctly(self):
        from src.workflow5.ops import transition_jira_to_in_review
        transitions_tool = _make_tool(
            "JIRA_GET_TRANSITIONS",
            run_return={"transitions": [{"id": "31", "name": "In Review"}]},
        )
        transition_tool = _make_tool("JIRA_TRANSITION_ISSUE", run_return={"successful": True})
        result = transition_jira_to_in_review(
            jira_tools=[transitions_tool, transition_tool],
            ticket_key="LEADS-10",
        )
        assert result == "transitioned:In Review"
        transition_tool.run.assert_called_once()

    def test_skips_when_no_match(self):
        from src.workflow5.ops import transition_jira_to_in_review
        transitions_tool = _make_tool(
            "JIRA_GET_TRANSITIONS",
            run_return={"transitions": [{"id": "11", "name": "To Do"}, {"id": "21", "name": "In Progress"}]},
        )
        transition_tool = _make_tool("JIRA_TRANSITION_ISSUE")
        result = transition_jira_to_in_review(
            jira_tools=[transitions_tool, transition_tool],
            ticket_key="LEADS-10",
        )
        assert result == "skipped:no-in-review-transition"
        transition_tool.run.assert_not_called()

    def test_skips_when_no_tool(self):
        from src.workflow5.ops import transition_jira_to_in_review
        result = transition_jira_to_in_review(
            jira_tools=[],
            ticket_key="LEADS-10",
        )
        assert result == "skipped:no-tool"


class TestPostGithubNoTicketWarning:

    def test_posts_comment(self):
        from src.workflow5.ops import post_github_no_ticket_warning
        tool = _make_tool("GITHUB_CREATE_AN_ISSUE_COMMENT", run_return={"id": 1})
        result = post_github_no_ticket_warning(
            github_tools=[tool],
            owner="org",
            repo="repo",
            issue_number=43,
        )
        assert result == "posted"
        tool.run.assert_called_once()

    def test_skips_when_no_tool(self):
        from src.workflow5.ops import post_github_no_ticket_warning
        result = post_github_no_ticket_warning(
            github_tools=[],
            owner="org",
            repo="repo",
            issue_number=43,
        )
        assert result == "skipped:no-tool"


# ── Wrapper-layer tests ─────────────────────────────────────────────────────

class TestRunJiraLinkCrew:

    @patch("src.jira_link_crew.run_workflow5")
    @patch("src.jira_link_crew.build_tools", return_value=[])
    @patch("src.jira_link_crew.composio_user_id", return_value="default")
    def test_builds_tools_and_calls_runner(self, mock_uid, mock_build, mock_run):
        mock_run.return_value = CrewRunResult(raw="linked: PR #1 -> LEADS-1", model="rule-engine")
        from src.jira_link_crew import run_jira_link_crew
        result = run_jira_link_crew(payload=_pr_payload())
        assert isinstance(result, CrewRunResult)
        assert "linked" in result.raw
        mock_run.assert_called_once()

    @patch("src.jira_link_crew.run_workflow5")
    @patch("src.jira_link_crew.build_tools", return_value=[])
    @patch("src.jira_link_crew.composio_user_id", return_value="test-user-42")
    def test_uses_composio_user_id(self, mock_uid, mock_build, mock_run):
        mock_run.return_value = CrewRunResult(raw="ok", model="rule-engine")
        from src.jira_link_crew import run_jira_link_crew
        run_jira_link_crew(payload=_pr_payload())
        calls = mock_build.call_args_list
        for call in calls:
            assert call.kwargs["user_id"] == "test-user-42"


# ── Endpoint-layer tests (additions to main.py behaviour) ───────────────────

class TestGithubWebhookWf5Integration:

    @pytest.fixture
    def client(self):
        from src.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    @patch("src.main.run_jira_link_crew")
    @patch("src.main.run_pr_review_crew")
    def test_github_webhook_calls_both_wf4_and_wf5(self, mock_wf4, mock_wf5, client):
        mock_wf4.return_value = CrewRunResult(raw="updated: PR #1", model="rule-engine")
        mock_wf5.return_value = CrewRunResult(raw="linked: PR #1 -> LEADS-1", model="rule-engine")
        response = client.post("/webhooks/github", json=_pr_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "updated: PR #1"
        assert data["wf5_result"] == "linked: PR #1 -> LEADS-1"
        mock_wf4.assert_called_once()
        mock_wf5.assert_called_once()

    @patch("src.main.run_jira_link_crew", side_effect=Exception("wf5 boom"))
    @patch("src.main.run_pr_review_crew")
    def test_github_webhook_wf5_failure_does_not_block_wf4(self, mock_wf4, mock_wf5, client):
        mock_wf4.return_value = CrewRunResult(raw="updated: PR #1", model="rule-engine")
        response = client.post("/webhooks/github", json=_pr_payload())
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "updated: PR #1"
        assert data["wf5_result"] == "skipped:wf5-error"

    @patch("src.main.run_jira_link_crew")
    @patch("src.main.run_pr_review_crew", side_effect=RuntimeError("missing env"))
    def test_github_webhook_wf4_runtime_error_returns_400(self, mock_wf4, mock_wf5, client):
        response = client.post("/webhooks/github", json=_pr_payload())
        assert response.status_code == 400
        assert "missing env" in response.json()["detail"]
        mock_wf5.assert_not_called()
