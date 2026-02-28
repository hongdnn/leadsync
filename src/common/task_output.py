"""Task output extraction helper shared by all crews."""

from typing import Any


def extract_task_output(task: Any) -> str:
    """
    Read normalized text output from a CrewAI task.

    Args:
        task: CrewAI task-like object.
    Returns:
        Output text when present, else empty string.
    """
    output = getattr(task, "output", None)
    if output is None:
        return ""
    if isinstance(output, str):
        return output.strip()
    raw = getattr(output, "raw", None)
    if isinstance(raw, str):
        return raw.strip()
    result = getattr(output, "result", None)
    if isinstance(result, str):
        return result.strip()
    return ""
