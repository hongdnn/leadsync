"""Crew kickoff retry helper for model alias and transient LLM failures."""

import logging
from typing import Any

from src.stream import make_event, manager

EMPTY_LLM_RESPONSE_MESSAGE = "Invalid response from LLM call - None or empty."


def _is_empty_llm_response_error(exc: Exception) -> bool:
    """Return True when CrewAI surfaced an empty/None LLM response failure."""
    return EMPTY_LLM_RESPONSE_MESSAGE in str(exc)


def _fallback_model_for_error(model: str, exc: Exception) -> str | None:
    """
    Select fallback model for known failure signatures.

    Args:
        model: Preferred model name.
        exc: Exception raised by crew kickoff.
    Returns:
        Fallback model name when known; otherwise None.
    """
    error_text = str(exc)
    if "-latest" in model and "NOT_FOUND" in error_text:
        return model.replace("-latest", "")
    if "flash-lite" in model and (
        "NOT_FOUND" in error_text or _is_empty_llm_response_error(exc)
    ):
        return model.replace("flash-lite", "flash")
    if "2.5-flash" in model and _is_empty_llm_response_error(exc):
        return model.replace("2.5-flash", "2.0-flash")
    return None


def _drain_streaming_output(result: Any, label: str) -> Any:
    """Drain streaming chunks from a CrewStreamingOutput, broadcasting each.

    If *result* is a normal CrewOutput (non-streaming), it passes through unchanged.

    Args:
        result: Return value of crew.kickoff() — may be streaming or plain.
        label: Workflow label for event metadata.
    Returns:
        The final CrewOutput object.
    """
    try:
        from crewai.types.streaming import CrewStreamingOutput
    except ImportError:
        return result

    if not isinstance(result, CrewStreamingOutput):
        return result

    for chunk in result:
        chunk_type = getattr(chunk, "type", "TEXT")
        type_str = str(chunk_type).split(".")[-1].lower()
        event_type = "tool_call" if type_str == "tool_call" else "chunk"
        manager.broadcast_sync(make_event(
            event_type,
            label,
            agent_role=getattr(chunk, "agent_role", "") or "",
            task_name=getattr(chunk, "task_name", "") or "",
            content=getattr(chunk, "content", "") or str(chunk),
            chunk_type=type_str,
            tool_name=getattr(chunk, "tool_name", "") or "",
        ))

    return getattr(result, "result", result)


def kickoff_with_model_fallback(
    *,
    crew: Any,
    model: str,
    agents: list[Any],
    logger: logging.Logger,
    label: str,
) -> tuple[Any, str]:
    """
    Run crew kickoff with targeted retries for known model/runtime failures.

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
        return _drain_streaming_output(crew.kickoff(), label), model
    except Exception as exc:
        logger.exception("%s crew kickoff failed for model '%s'.", label, model)
        effective_exc = exc

        # Retry once for transient empty LLM responses from provider/tool routing.
        if _is_empty_llm_response_error(exc):
            logger.warning(
                "Retrying %s crew once for transient empty LLM response on model '%s'.",
                label,
                model,
            )
            try:
                return _drain_streaming_output(crew.kickoff(), label), model
            except Exception as retry_exc:
                logger.exception(
                    "%s crew retry still failed for model '%s'.", label, model
                )
                effective_exc = retry_exc

        fallback_model = _fallback_model_for_error(model, effective_exc)
        if fallback_model and fallback_model != model:
            logger.warning(
                "Retrying %s crew with fallback model '%s'.", label, fallback_model
            )
            for agent in agents:
                agent.llm = fallback_model
            return _drain_streaming_output(crew.kickoff(), label), fallback_model
        raise effective_exc
