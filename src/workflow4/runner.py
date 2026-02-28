"""Workflow 4 runner: auto-generate PR details from code changes."""

import logging
from typing import Any

from src.shared import CrewRunResult
from src.workflow4.ai_writer import generate_ai_sections
from src.workflow4.enrichment import _clean_summary, render_full_pr_details
from src.workflow4.ops import list_pr_files, upsert_pr_body
from src.workflow4.parsing import parse_pr_context

GITHUB_ACTIONS_TO_PROCESS = {"opened", "reopened", "synchronize", "ready_for_review"}
logger = logging.getLogger(__name__)


def run_workflow4(payload: dict[str, Any], github_tools: list[Any], jira_tools: list[Any]) -> CrewRunResult:
    """Generate and update pull request details automatically."""
    _ = jira_tools
    pr = parse_pr_context(payload)
    model = "rule-engine"

    if pr.action not in GITHUB_ACTIONS_TO_PROCESS:
        return CrewRunResult(raw=f"skipped: unsupported action '{pr.action}'", model=model)
    if not pr.number or not pr.owner or not pr.repo:
        return CrewRunResult(raw="skipped: missing pull request metadata", model=model)
    logger.warning(
        "Workflow4 run: action=%s owner=%s repo=%s pr=%s ticket=%s",
        pr.action,
        pr.owner,
        pr.repo,
        pr.number,
        pr.jira_key or "N/A",
    )
    files = list_pr_files(
        github_tools,
        pr.owner,
        pr.repo,
        pr.number,
        base_sha=pr.base_sha,
        head_sha=pr.head_sha,
    )
    logger.warning("Workflow4 diff collection: files=%d", len(files))

    ai_summary: str | None = None
    ai_implementation: list[str] | None = None
    ai_validation: list[str] | None = None
    ai_title: str = ""
    ai_used = False
    if files:
        try:
            ai_sections = generate_ai_sections(
                ticket_key=pr.jira_key,
                pr_title=pr.title,
                files=files,
            )
            ai_title = ai_sections.suggested_title
            ai_summary = ai_sections.summary
            ai_implementation = [f"- {line}" for line in ai_sections.implementation_details]
            ai_validation = [f"- {line}" for line in ai_sections.suggested_validation]
            ai_used = True
        except Exception:
            logger.exception("Workflow4 AI generation failed; using deterministic fallback.")
            ai_title = ""
            ai_summary = None
            ai_implementation = None
            ai_validation = None

    details_block = render_full_pr_details(
        ticket_key=pr.jira_key,
        pr_title=pr.title,
        files=files,
        summary_override=ai_summary,
        implementation_override=ai_implementation,
        validation_override=ai_validation,
    )

    # Always produce a title: prefer AI suggestion, fall back to cleaned summary/PR title.
    if not ai_title:
        ai_title = _clean_summary(ai_summary or pr.title, pr.jira_key)
    logger.warning("Workflow4 final title: '%s'", ai_title)

    upsert_pr_body(github_tools, pr.owner, pr.repo, pr.number, details_block, title=ai_title)
    logger.warning(
        "Workflow4 PR body updated: pr=%s files=%d ai_used=%s",
        pr.number,
        len(files),
        str(ai_used).lower(),
    )
    return CrewRunResult(
        raw=(
            f"updated: PR #{pr.number} ({pr.jira_key or 'no-ticket-key'}) auto-details action={pr.action} "
            f"files={len(files)} ai_used={str(ai_used).lower()}"
        ),
        model=model,
    )
