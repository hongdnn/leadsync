"""Workflow 4 runner: auto-generate PR details from code changes."""

from typing import Any

from src.shared import CrewRunResult
from src.workflow4.enrichment import (
    render_full_pr_details,
    upsert_enrichment_block,
)
from src.workflow4.ops import list_pr_files, upsert_pr_body
from src.workflow4.parsing import parse_pr_context

GITHUB_ACTIONS_TO_PROCESS = {"opened", "reopened", "synchronize", "edited", "ready_for_review"}


def run_workflow4(payload: dict[str, Any], github_tools: list[Any], jira_tools: list[Any]) -> CrewRunResult:
    """Generate and update pull request details automatically."""
    _ = jira_tools
    pr = parse_pr_context(payload)
    model = "rule-engine"

    if pr.action not in GITHUB_ACTIONS_TO_PROCESS:
        return CrewRunResult(raw=f"skipped: unsupported action '{pr.action}'", model=model)
    if not pr.number or not pr.owner or not pr.repo:
        return CrewRunResult(raw="skipped: missing pull request metadata", model=model)
    files = list_pr_files(github_tools, pr.owner, pr.repo, pr.number)

    details_block = render_full_pr_details(
        ticket_key=pr.jira_key,
        pr_title=pr.title,
        files=files,
    )
    updated_body = upsert_enrichment_block(pr.body, details_block)

    upsert_pr_body(github_tools, pr.owner, pr.repo, pr.number, updated_body)
    return CrewRunResult(
        raw=(
            f"updated: PR #{pr.number} ({pr.jira_key or 'no-ticket-key'}) auto-details action={pr.action} "
            f"files={len(files)}"
        ),
        model=model,
    )
