"""CrewAI writer for PR summary and implementation details from actual diffs."""

from dataclasses import dataclass
import json
import logging
import re
from typing import Any

from crewai import Agent, Crew, Process, Task

from src.common.model_retry import kickoff_with_model_fallback
from src.common.task_output import extract_task_output
from src.shared import build_llm

logger = logging.getLogger(__name__)


@dataclass
class AISections:
    """Structured AI output sections for PR body."""

    summary: str
    implementation_details: list[str]
    suggested_validation: list[str]


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = (text or "").strip()
    if not stripped:
        raise RuntimeError("Empty AI output for PR sections.")

    fence = re.search(r"```json\s*(\{.*\})\s*```", stripped, flags=re.DOTALL)
    candidate = fence.group(1) if fence else stripped

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError("AI output did not include a JSON object.")
    payload = candidate[start : end + 1]
    return json.loads(payload)


def _normalize_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for item in value:
        line = str(item).strip()
        if not line:
            continue
        lines.append(line)
    return lines


def _build_diff_context(files: list[dict[str, Any]], *, max_chars: int = 16000) -> str:
    sections: list[str] = []
    consumed = 0
    for file in files:
        filename = str(file.get("filename") or "unknown")
        status = str(file.get("status") or "modified")
        additions = int(file.get("additions") or 0)
        deletions = int(file.get("deletions") or 0)
        patch = str(file.get("patch") or "").strip()
        header = f"FILE: {filename} ({status}, +{additions}/-{deletions})"
        body = patch if patch else "(patch unavailable)"
        chunk = f"{header}\n{body}\n"
        if consumed + len(chunk) > max_chars:
            break
        sections.append(chunk)
        consumed += len(chunk)
    return "\n".join(sections).strip()


def generate_ai_sections(*, ticket_key: str, pr_title: str, files: list[dict[str, Any]]) -> AISections:
    """Use CrewAI to infer summary and implementation details from diff snippets."""
    model = build_llm()
    diff_context = _build_diff_context(files)
    if not diff_context:
        raise RuntimeError("No diff context available for AI summary.")
    logger.warning(
        "Workflow4 AI writer start: ticket=%s files=%d diff_chars=%d model=%s",
        ticket_key or "N/A",
        len(files),
        len(diff_context),
        model,
    )

    writer = Agent(
        role="PR Description Writer",
        goal="Write precise PR summary and implementation details from actual code diffs.",
        backstory=(
            "You are a senior reviewer who writes concise, factual pull request descriptions "
            "based only on the provided code changes."
        ),
        verbose=True,
        llm=model,
    )

    task = Task(
        description=(
            "Generate PR sections using ONLY the diff context below.\n"
            "Do not invent architecture not present in diffs.\n"
            "Return STRICT JSON with keys:\n"
            "summary: string\n"
            "implementation_details: string[]\n"
            "suggested_validation: string[]\n\n"
            f"Ticket key: {ticket_key or 'N/A'}\n"
            f"PR title: {pr_title or 'N/A'}\n\n"
            f"Diff context:\n{diff_context}\n"
        ),
        expected_output="Strict JSON object with summary, implementation_details, suggested_validation.",
        agent=writer,
    )

    crew = Crew(
        agents=[writer],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )
    kickoff_with_model_fallback(
        crew=crew,
        model=model,
        agents=[writer],
        logger=logger,
        label="Workflow4-PRWriter",
    )
    output = extract_task_output(task)
    logger.warning("Workflow4 AI writer raw output: %s", output[:1200])
    data = _extract_json_object(output)

    summary = str(data.get("summary") or "").strip()
    if not summary:
        raise RuntimeError("AI output missing summary.")

    implementation = _normalize_lines(data.get("implementation_details"))
    validation = _normalize_lines(data.get("suggested_validation"))
    if not implementation:
        raise RuntimeError("AI output missing implementation details.")
    if not validation:
        validation = ["Run relevant unit/integration tests for touched modules."]

    result = AISections(
        summary=summary,
        implementation_details=implementation,
        suggested_validation=validation,
    )
    logger.warning(
        "Workflow4 AI writer parsed: summary_len=%d impl_items=%d validation_items=%d",
        len(result.summary),
        len(result.implementation_details),
        len(result.suggested_validation),
    )
    return result
