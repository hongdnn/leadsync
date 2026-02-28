"""
src/leadsync_crew.py
Workflow 1: Ticket Enrichment — Context Gatherer → Intent Reasoner → Propagator.
Exports: run_leadsync_crew(payload) -> CrewRunResult
"""

import logging
from pathlib import Path
import re
from typing import Any

from crewai import Agent, Crew, Process, Task

from src.config import Config
from src.jira_history import build_same_label_progress_context, extract_primary_label
from src.shared import CrewRunResult
from src.tools.jira_tools import get_agent_tools

logger = logging.getLogger(__name__)
ARTIFACT_DIR = Path("artifacts") / "workflow1"


def _tool_name_set(tools: list[Any]) -> set[str]:
    return {getattr(tool, "name", "").upper() for tool in tools}


def _has_tool_prefix(tool_names: set[str], prefix: str) -> bool:
    """Return whether any tool name starts with prefix."""
    upper = prefix.upper()
    return any(name.startswith(upper) for name in tool_names)


def _safe_dict(value: Any) -> dict[str, Any]:
    """Return value when dict-like, otherwise return empty dict."""
    return value if isinstance(value, dict) else {}


def _required_sections() -> list[str]:
    """
    Return required Workflow 1 markdown sections.

    Returns:
        Ordered section headings required by the roadmap.
    """
    return [
        "## Task",
        "## Context",
        "## Constraints",
        "## Implementation Rules",
        "## Expected Output",
    ]


def _has_required_sections(markdown: str) -> bool:
    """
    Check whether markdown includes all required section headings.

    Args:
        markdown: Candidate markdown content.
    Returns:
        True when all required headings exist.
    """
    return all(section in markdown for section in _required_sections())


def _extract_task_output(task: Task) -> str:
    """
    Read task output text from a CrewAI Task.

    Args:
        task: CrewAI Task instance.
    Returns:
        Extracted text output, or empty string when unavailable.
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


def _extract_text(value: Any) -> str:
    """
    Extract plain text from string/ADF-like values.

    Args:
        value: Candidate content from Jira payload.
    Returns:
        Best-effort plain text.
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_extract_text(item) for item in value]
        return " ".join(part for part in parts if part)
    if isinstance(value, dict):
        text_value = value.get("text")
        if isinstance(text_value, str):
            return text_value.strip()
        return _extract_text(value.get("content"))
    return ""


def _normalize_tokens(values: list[str]) -> list[str]:
    """
    Normalize labels/components into lowercase matching tokens.

    Args:
        values: Raw label or component values.
    Returns:
        Flattened token list for robust matching.
    """
    tokens: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        lowered = value.lower().strip()
        if not lowered:
            continue
        tokens.append(lowered)
        tokens.extend(token for token in re.split(r"[^a-z0-9]+", lowered) if token)
    return tokens


def _select_ruleset_file(labels: list[str], component_names: list[str]) -> str:
    """
    Select ruleset file based on Jira labels/components.

    Args:
        labels: Jira label values.
        component_names: Jira component names.
    Returns:
        Ruleset file name under templates/.
    """
    category_map: list[tuple[str, set[str]]] = [
        ("frontend-ruleset.md", {"frontend", "front", "ui", "ux", "fe", "client", "react"}),
        ("db-ruleset.md", {"database", "db", "sql", "schema", "migration", "postgres"}),
        ("backend-ruleset.md", {"backend", "back", "api", "service", "be", "server"}),
    ]
    tokens = _normalize_tokens(labels) + _normalize_tokens(component_names)
    for file_name, keywords in category_map:
        if any(token in keywords for token in tokens):
            return file_name
    return "backend-ruleset.md"


def _normalize_prompt_markdown(
    reasoner_text: str,
    issue_key: str,
    summary: str,
    gathered_context: str,
    ruleset_content: str,
) -> str:
    """
    Ensure generated prompt markdown has the required section structure.

    Args:
        reasoner_text: Raw text produced by the reasoner task.
        issue_key: Jira issue key.
        summary: Issue summary line.
        gathered_context: Gatherer task output text.
        ruleset_content: Label-mapped ruleset markdown.
    Returns:
        Markdown string containing all required headings.
    """
    if reasoner_text and _has_required_sections(reasoner_text):
        return reasoner_text.strip() + "\n"

    summary_text = summary.strip() or "No summary provided."
    context_text = gathered_context.strip() or "No additional context gathered."
    constraints_text = (
        "- Stay aligned with Jira scope and linked context.\n"
        "- Keep output paste-ready for the assignee.\n"
        "- Follow repository standards and existing patterns."
    )
    rules_text = ruleset_content.strip() or "- No ruleset content found; use backend defaults."
    expected_output_text = (
        reasoner_text.strip()
        or "Provide an implementation-ready prompt with code, tests, and docs checklist."
    )

    return (
        "## Task\n"
        f"- Ticket: {issue_key}\n"
        f"- Summary: {summary_text}\n\n"
        "## Context\n"
        f"{context_text}\n\n"
        "## Constraints\n"
        f"{constraints_text}\n\n"
        "## Implementation Rules\n"
        f"{rules_text}\n\n"
        "## Expected Output\n"
        f"{expected_output_text}\n"
    )


def _safe_issue_key_for_filename(issue_key: str) -> str:
    """
    Sanitize issue key for safe filesystem usage.

    Args:
        issue_key: Jira issue key from payload.
    Returns:
        Safe key for filename usage.
    """
    return re.sub(r"[^A-Za-z0-9_.-]", "-", issue_key or "UNKNOWN")


def _write_prompt_file(issue_key: str, markdown: str) -> Path:
    """
    Persist prompt markdown artifact to disk.

    Args:
        issue_key: Jira issue key.
        markdown: Prompt markdown content.
    Returns:
        Absolute path to the written markdown file.
    Side effects:
        Creates artifact directory and writes prompt file.
    """
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    safe_key = _safe_issue_key_for_filename(issue_key)
    prompt_path = ARTIFACT_DIR / f"prompt-{safe_key}.md"
    prompt_path.write_text(markdown, encoding="utf-8")
    return prompt_path.resolve()


def _find_tool_by_name(tools: list[Any], name: str) -> Any | None:
    """
    Find first tool by exact uppercased name.

    Args:
        tools: List of CrewAI-compatible tools.
        name: Tool name to locate.
    Returns:
        Tool object when found, else None.
    """
    expected = name.upper()
    for tool in tools:
        if getattr(tool, "name", "").upper() == expected:
            return tool
    return None


def _attach_prompt_file(tools: list[Any], issue_key: str, file_path: Path) -> Any:
    """
    Attach a local markdown prompt file to a Jira issue via Composio.

    Args:
        tools: Composio tools available for Workflow 1.
        issue_key: Jira issue key.
        file_path: Local prompt file path.
    Returns:
        Raw tool response.
    Raises:
        RuntimeError: If attachment tool is unavailable.
        Exception: Any attachment call failure.
    """
    attachment_tool = _find_tool_by_name(tools, "JIRA_ADD_ATTACHMENT")
    if attachment_tool is None:
        raise RuntimeError("JIRA_ADD_ATTACHMENT tool is required for Workflow 1.")

    resolved_path = file_path.resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Prompt file not found for attachment: {resolved_path}")

    return attachment_tool.run(
        issue_key=issue_key,
        local_file_path=str(resolved_path),
        file_to_upload=str(resolved_path),
    )


def run_leadsync_crew(payload: dict[str, Any]) -> CrewRunResult:
    """
    Run the Ticket Enrichment crew for a Jira webhook payload.

    Args:
        payload: Jira webhook JSON body.
    Returns:
        CrewRunResult with raw crew output and model used.
    Raises:
        RuntimeError: If required env vars are missing.
        Exception: If crew.kickoff() fails and fallback also fails.
    Side effects:
        Writes back to Jira via Composio tools.
    """
    Config.require_gemini_api_key()
    model = Config.get_gemini_model()
    tools = get_agent_tools()
    tool_names = _tool_name_set(tools)

    has_jira_get_issue = "JIRA_GET_ISSUE" in tool_names
    has_jira_edit_issue = "JIRA_EDIT_ISSUE" in tool_names
    has_jira_add_comment = "JIRA_ADD_COMMENT" in tool_names
    has_jira_add_attachment = "JIRA_ADD_ATTACHMENT" in tool_names
    has_github_tools = _has_tool_prefix(tool_names, "GITHUB_")

    issue = _safe_dict(payload.get("issue"))
    if not issue:
        issue = _safe_dict(payload.get("workItem"))
    fields = _safe_dict(issue.get("fields"))

    issue_key = issue.get("key", issue.get("id", "UNKNOWN"))
    summary = fields.get("summary", issue.get("summary", ""))
    issue_description = _extract_text(fields.get("description", issue.get("description", "")))
    labels = fields.get("labels", issue.get("labels", []))
    if not isinstance(labels, list):
        labels = []
    primary_label = extract_primary_label(labels)

    assignee_data = _safe_dict(fields.get("assignee"))
    if not assignee_data:
        assignee_data = _safe_dict(issue.get("assignee"))
    assignee = (
        assignee_data.get("displayName")
        or assignee_data.get("display_name")
        or assignee_data.get("name")
        or "Unassigned"
    )

    project = _safe_dict(fields.get("project"))
    if not project:
        project = _safe_dict(issue.get("project"))
    project_key = project.get("key", "")

    components = fields.get("components", issue.get("components", []))
    if not isinstance(components, list):
        components = []
    component_names = [c.get("name", "") for c in components if isinstance(c, dict)]

    ruleset_file = _select_ruleset_file(labels=labels, component_names=component_names)
    ruleset_path = Path(__file__).parent.parent / "templates" / ruleset_file
    ruleset_content = ruleset_path.read_text(encoding="utf-8") if ruleset_path.exists() else ""

    common_context = (
        f"Issue key: {issue_key}\n"
        f"Summary: {summary}\n"
        f"Description: {issue_description or 'No description provided.'}\n"
        f"Labels: {labels}\n"
        f"Primary label: {primary_label or 'N/A'}\n"
        f"Assignee: {assignee}\n"
        f"Project: {project_key}\n"
        f"Components: {component_names}\n"
    )
    same_label_history = build_same_label_progress_context(
        tools=tools,
        project_key=project_key,
        label=primary_label,
        exclude_issue_key=str(issue_key),
        limit=10,
    )
    common_context += f"Same-label history context:\n{same_label_history}\n"

    gatherer = Agent(
        role="Context Gatherer",
        goal="Collect Jira and GitHub context needed to implement the issue correctly.",
        backstory=(
            "You are responsible for finding relevant context from Jira and recent "
            "commits on the main branch."
        ),
        verbose=True,
        tools=tools if has_jira_get_issue else [],
        llm=model,
    )

    reasoner = Agent(
        role="Intent Reasoner",
        goal="Create a personalized implementation prompt based on ticket labels and context.",
        backstory=(
            "You map issue labels to a ruleset and generate a copy-paste-ready prompt "
            "for the assigned developer."
        ),
        verbose=True,
        llm=model,
    )

    propagator = Agent(
        role="Propagator",
        goal="Write the generated context and instructions back to the Jira issue.",
        backstory=(
            "You update the Jira ticket with a concise summary and add a final comment "
            "that the prompt is ready."
        ),
        verbose=True,
        tools=tools,
        llm=model,
    )

    gather_task = Task(
        description=(
            "Gather context for this issue.\n"
            f"{common_context}\n"
            f"Available tool names: {sorted(tool_names)}\n"
            "Rules:\n"
            f"- JIRA_GET_ISSUE available: {has_jira_get_issue}\n"
            f"- Any GITHUB_* tools available: {has_github_tools}\n"
            "- If unavailable, do not call Jira read tools and use payload context only.\n"
            "- If GITHUB tools are available, scan repository context for files/modules that match the "
            "ticket summary, description, labels, and components.\n"
            "Required output:\n"
            "1) Relevant linked/recent Jira issue summary\n"
            "2) Last 24h main-branch commits related to this issue scope\n"
            "3) Risks/constraints discovered\n"
            "4) Summary of previous progress from the latest 10 completed same-label tickets\n"
            "5) 3-8 source files or modules likely impacted, with one-line rationale each\n"
        ),
        expected_output="A structured context summary with commits, related issues, and constraints.",
        agent=gatherer,
    )

    reason_task = Task(
        description=(
            "From gathered context, generate:\n"
            "1) One markdown document with these exact sections in order:\n"
            "   - ## Task\n"
            "   - ## Context\n"
            "   - ## Constraints\n"
            "   - ## Implementation Rules\n"
            "   - ## Expected Output\n"
            "2) In the Context section, include a concise summary of previous same-label completed "
            "work so the assignee sees what has already been completed in this development phase.\n"
            f"3) Apply rules from selected ruleset '{ruleset_file}':\n{ruleset_content}\n"
            "4) Add implementation output checklist (code/tests/docs)\n"
            "5) Keep tone technical and execution-oriented. Avoid broad ticket summaries.\n"
            f"{common_context}"
        ),
        expected_output=(
            "Markdown containing exactly the five required sections for prompt-[ticket-key].md."
        ),
        agent=reasoner,
        context=[gather_task],
    )

    propagate_task = Task(
        description=(
            "Write back to Jira:\n"
            f"Available tool names: {sorted(tool_names)}\n"
            f"- JIRA_ADD_COMMENT available: {has_jira_add_comment}\n"
            f"- JIRA_EDIT_ISSUE available: {has_jira_edit_issue}\n"
            f"- JIRA_ADD_ATTACHMENT available: {has_jira_add_attachment}\n"
            "Rules:\n"
            "- Always use issue key from context.\n"
            "- If JIRA_ADD_COMMENT is available, add plain-text technical execution guidance without markdown syntax.\n"
            "- Comment structure (plain text, no '#', no bullet markers):\n"
            "  1) One line: 'Previous same-label progress:'\n"
            "  2) 3-5 short lines of completed technical work from recent same-label tickets.\n"
            "  3) One line: 'Recommended implementation path for current task:'\n"
            "  4) 3-5 short lines: concrete steps, likely files/modules, validation checks.\n"
            "- Only update issue description when JIRA_EDIT_ISSUE is available.\n"
            "- For issue description updates, write technical execution guidance (approach, code areas, risks, test plan) "
            "instead of a generic summary.\n"
            "- For issue description updates, avoid opening like 'This ticket ...' or 'This task ...'.\n"
            "- Mention that a prompt markdown attachment will be added when available.\n"
            "- Do NOT write meta/system statements such as 'the ticket has been enriched' or "
            "'it is now ready for development'. Keep wording developer-facing and concrete.\n"
            "- Never call any tool that is not listed in available tool names."
        ),
        expected_output="Confirmation of Jira write-back actions taken.",
        agent=propagator,
        context=[reason_task],
    )

    crew = Crew(
        agents=[gatherer, reasoner, propagator],
        tasks=[gather_task, reason_task, propagate_task],
        process=Process.sequential,
        verbose=True,
    )
    try:
        result = crew.kickoff()
        used_model = model
    except Exception as exc:
        logger.exception("LeadSync crew kickoff failed for model '%s'.", model)
        if "-latest" in model and "NOT_FOUND" in str(exc):
            fallback_model = model.replace("-latest", "")
            logger.warning("Retrying LeadSync crew with fallback model '%s'.", fallback_model)
            gatherer.llm = fallback_model
            reasoner.llm = fallback_model
            propagator.llm = fallback_model
            result = crew.kickoff()
            used_model = fallback_model
        else:
            raise

    try:
        gathered_context = _extract_task_output(gather_task)
        reasoner_text = _extract_task_output(reason_task)
        prompt_markdown = _normalize_prompt_markdown(
            reasoner_text=reasoner_text,
            issue_key=issue_key,
            summary=summary,
            gathered_context=gathered_context,
            ruleset_content=ruleset_content,
        )
        prompt_path = _write_prompt_file(issue_key=issue_key, markdown=prompt_markdown)
        _attach_prompt_file(tools=tools, issue_key=issue_key, file_path=prompt_path)
        logger.info(
            "Workflow 1 prompt file generated and attached for issue '%s': %s",
            issue_key,
            prompt_path,
        )
    except Exception:
        logger.exception("Workflow 1 prompt artifact handling failed for issue '%s'.", issue_key)
        raise

    return CrewRunResult(raw=str(result), model=used_model)
