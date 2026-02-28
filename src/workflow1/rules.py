"""Workflow 1 ruleset selection helpers."""

from pathlib import Path

from src.common.token_matching import normalize_tokens

CATEGORY_MAP: list[tuple[str, set[str]]] = [
    ("frontend-ruleset.md", {"frontend", "front", "ui", "ux", "fe", "client", "react"}),
    ("db-ruleset.md", {"database", "db", "sql", "schema", "migration", "postgres"}),
    ("backend-ruleset.md", {"backend", "back", "api", "service", "be", "server"}),
]


def select_ruleset_file(labels: list[str], component_names: list[str]) -> str:
    """Select ruleset filename from Jira labels/components."""
    tokens = normalize_tokens(labels) + normalize_tokens(component_names)
    for file_name, keywords in CATEGORY_MAP:
        if any(token in keywords for token in tokens):
            return file_name
    return "backend-ruleset.md"


def load_ruleset_content(file_name: str) -> str:
    """Read selected ruleset content from `templates/` when present."""
    path = Path(__file__).parents[2] / "templates" / file_name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
