"""Unit tests for src/common/model_retry.py."""

from unittest.mock import MagicMock

import pytest


def test_kickoff_with_model_fallback_returns_on_first_success():
    from src.common.model_retry import kickoff_with_model_fallback

    crew = MagicMock()
    crew.kickoff.return_value = "ok"
    agents = [MagicMock(llm="gemini/gemini-2.5-flash")]
    logger = MagicMock()

    result, used_model = kickoff_with_model_fallback(
        crew=crew,
        model="gemini/gemini-2.5-flash",
        agents=agents,
        logger=logger,
        label="Digest",
    )

    assert result == "ok"
    assert used_model == "gemini/gemini-2.5-flash"
    assert crew.kickoff.call_count == 1


def test_kickoff_with_model_fallback_retries_once_on_empty_llm_response():
    from src.common.model_retry import kickoff_with_model_fallback

    crew = MagicMock()
    crew.kickoff.side_effect = [
        Exception("Invalid response from LLM call - None or empty."),
        "ok-after-retry",
    ]
    agents = [MagicMock(llm="gemini/gemini-2.5-flash")]
    logger = MagicMock()

    result, used_model = kickoff_with_model_fallback(
        crew=crew,
        model="gemini/gemini-2.5-flash",
        agents=agents,
        logger=logger,
        label="Digest",
    )

    assert result == "ok-after-retry"
    assert used_model == "gemini/gemini-2.5-flash"
    assert crew.kickoff.call_count == 2


def test_kickoff_with_model_fallback_uses_latest_not_found_fallback():
    from src.common.model_retry import kickoff_with_model_fallback

    crew = MagicMock()
    crew.kickoff.side_effect = [Exception("Model NOT_FOUND"), "ok-with-fallback"]
    agent = MagicMock(llm="gemini/gemini-2.5-flash-latest")
    logger = MagicMock()

    result, used_model = kickoff_with_model_fallback(
        crew=crew,
        model="gemini/gemini-2.5-flash-latest",
        agents=[agent],
        logger=logger,
        label="Digest",
    )

    assert result == "ok-with-fallback"
    assert used_model == "gemini/gemini-2.5-flash"
    assert agent.llm == "gemini/gemini-2.5-flash"
    assert crew.kickoff.call_count == 2


def test_kickoff_with_model_fallback_uses_flash_lite_fallback_after_empty_retry():
    from src.common.model_retry import kickoff_with_model_fallback

    crew = MagicMock()
    crew.kickoff.side_effect = [
        Exception("Invalid response from LLM call - None or empty."),
        Exception("Invalid response from LLM call - None or empty."),
        "ok-with-flash-fallback",
    ]
    agent = MagicMock(llm="gemini/gemini-2.5-flash-lite")
    logger = MagicMock()

    result, used_model = kickoff_with_model_fallback(
        crew=crew,
        model="gemini/gemini-2.5-flash-lite",
        agents=[agent],
        logger=logger,
        label="Digest",
    )

    assert result == "ok-with-flash-fallback"
    assert used_model == "gemini/gemini-2.5-flash"
    assert agent.llm == "gemini/gemini-2.5-flash"
    assert crew.kickoff.call_count == 3


def test_kickoff_with_model_fallback_raises_when_unhandled_failure():
    from src.common.model_retry import kickoff_with_model_fallback

    crew = MagicMock()
    crew.kickoff.side_effect = Exception("some unhandled failure")
    logger = MagicMock()

    with pytest.raises(Exception, match="some unhandled failure"):
        kickoff_with_model_fallback(
            crew=crew,
            model="gemini/gemini-2.5-pro",
            agents=[MagicMock(llm="gemini/gemini-2.5-pro")],
            logger=logger,
            label="Digest",
        )
