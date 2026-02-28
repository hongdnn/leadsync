"""Crew kickoff retry helper for `-latest` model fallback handling."""

import logging
from typing import Any


def kickoff_with_model_fallback(
    *,
    crew: Any,
    model: str,
    agents: list[Any],
    logger: logging.Logger,
    label: str,
) -> tuple[Any, str]:
    """
    Run crew kickoff and retry once when latest model alias is missing.

    Args:
        crew: CrewAI crew-like object with `kickoff()`.
        model: Preferred model name.
        agents: Agents whose `.llm` should be updated for fallback retry.
        logger: Logger instance for failure diagnostics.
        label: Workflow label for log messages.
    Returns:
        Tuple of (kickoff_result, used_model_name).
    """
    try:
        return crew.kickoff(), model
    except Exception as exc:
        logger.exception("%s crew kickoff failed for model '%s'.", label, model)
        if "-latest" in model and "NOT_FOUND" in str(exc):
            fallback_model = model.replace("-latest", "")
            logger.warning("Retrying %s crew with fallback model '%s'.", label, fallback_model)
            for agent in agents:
                agent.llm = fallback_model
            return crew.kickoff(), fallback_model
        raise
