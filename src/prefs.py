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
