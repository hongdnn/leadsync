"""Workflow 3 parsing helpers."""


def parse_slack_text(text: str) -> tuple[str, str]:
    """
    Split slash-command text into ticket key and question.

    Args:
        text: Raw text such as `LEADS-123 What is the approach?`.
    Returns:
        Tuple of (ticket_key, question).
    """
    parts = text.strip().split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""
