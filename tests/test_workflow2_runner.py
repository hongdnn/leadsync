"""Unit tests for Workflow 2 runner behavior."""

import logging
from unittest.mock import MagicMock, patch


def _build_runtime(acquire_lock: bool) -> object:
    from src.workflow2.runner import Workflow2Runtime

    return Workflow2Runtime(
        Agent=MagicMock(side_effect=lambda **kwargs: MagicMock(llm=kwargs.get("llm"))),
        Task=MagicMock(side_effect=lambda **kwargs: MagicMock(output=MagicMock(raw=""))),
        Crew=MagicMock(return_value=MagicMock()),
        Process=MagicMock(sequential="sequential"),
        memory_enabled=MagicMock(return_value=True),
        build_memory_db_path=MagicMock(return_value=":memory:"),
        record_event=MagicMock(),
        record_memory_item=MagicMock(),
        acquire_idempotency_lock=MagicMock(return_value=acquire_lock),
    )


@patch("src.workflow2.runner.kickoff_with_model_fallback")
def test_run_workflow2_uses_window_minutes_in_scan_prompt(mock_kickoff):
    from src.workflow2.runner import run_workflow2

    runtime = _build_runtime(acquire_lock=True)
    mock_kickoff.return_value = ("ok", "gemini/gemini-2.5-flash")
    logger = logging.getLogger("test-workflow2")

    run_workflow2(
        model="gemini/gemini-2.5-flash",
        slack_channel_id="C123",
        github_tools=[],
        slack_tools=[],
        runtime=runtime,
        logger=logger,
        window_minutes=60,
        run_source="manual",
        bucket_start_utc=None,
        repo_owner="acme",
        repo_name="leadsync",
        idempotency_enabled=True,
    )

    scan_task_description = runtime.Task.call_args_list[0].kwargs["description"]
    assert "since" in scan_task_description
    assert "NO_COMMITS" in scan_task_description
    assert "repository acme/leadsync" in scan_task_description
    assert "GITHUB_GET_A_COMMIT" in scan_task_description
    assert "SHA" in scan_task_description
    assert "AUTHOR" in scan_task_description
    assert "FILES" in scan_task_description
    assert "PATCH" in scan_task_description or "patch" in scan_task_description
    assert "30 lines" in scan_task_description


@patch("src.workflow2.runner.kickoff_with_model_fallback")
def test_run_workflow2_write_prompt_includes_no_commit_heartbeat_line(mock_kickoff):
    from src.workflow2.runner import run_workflow2

    runtime = _build_runtime(acquire_lock=True)
    mock_kickoff.return_value = ("ok", "gemini/gemini-2.5-flash")
    logger = logging.getLogger("test-workflow2")

    run_workflow2(
        model="gemini/gemini-2.5-flash",
        slack_channel_id="C123",
        github_tools=[],
        slack_tools=[],
        runtime=runtime,
        logger=logger,
        window_minutes=60,
        run_source="manual",
        bucket_start_utc=None,
        repo_owner="acme",
        repo_name="leadsync",
        idempotency_enabled=True,
    )

    write_task_description = runtime.Task.call_args_list[1].kwargs["description"]
    assert "No commits in the last 60 minutes." in write_task_description
    assert "AUTHORS" in write_task_description
    assert "COMMITS" in write_task_description
    assert "FILES" in write_task_description
    assert "CHANGES:" in write_task_description
    assert "patch" in write_task_description.lower()
    assert "function" in write_task_description.lower()


@patch("src.workflow2.runner.kickoff_with_model_fallback")
def test_run_workflow2_skips_duplicate_bucket_without_kickoff(mock_kickoff):
    from src.workflow2.runner import run_workflow2

    runtime = _build_runtime(acquire_lock=False)
    logger = logging.getLogger("test-workflow2")

    result = run_workflow2(
        model="gemini/gemini-2.5-flash",
        slack_channel_id="C123",
        github_tools=[],
        slack_tools=[],
        runtime=runtime,
        logger=logger,
        window_minutes=60,
        run_source="scheduled",
        bucket_start_utc="2026-02-28T11:00:00Z",
        repo_owner="acme",
        repo_name="leadsync",
        idempotency_enabled=True,
    )

    assert "skipped: duplicate bucket" in result.raw
    mock_kickoff.assert_not_called()
