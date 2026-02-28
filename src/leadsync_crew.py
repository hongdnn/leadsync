"""
src/leadsync_crew.py
Workflow 1: Ticket Enrichment — Context Gatherer → Intent Reasoner → Propagator.
Exports: run_leadsync_crew(payload) -> CrewRunResult
"""

from pathlib import Path
from typing import Any

from crewai import Agent, Crew, Process, Task

from src.config import Config
from src.shared import CrewRunResult
from src.tools.jira_tools import get_agent_tools


def _tool_name_set(tools: list[Any]) -> set[str]:
    return {getattr(tool, "name", "").upper() for tool in tools}


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
    Config.require_env("GOOGLE_API_KEY")
    model = Config.get_gemini_model()
    tools = get_agent_tools()
    tool_names = _tool_name_set(tools)

    has_jira_get_issue = "JIRA_GET_ISSUE" in tool_names
    has_jira_edit_issue = "JIRA_EDIT_ISSUE" in tool_names
    has_jira_add_comment = "JIRA_ADD_COMMENT" in tool_names

    issue_key = payload.get("issue", {}).get("key", "UNKNOWN")
    summary = payload.get("issue", {}).get("fields", {}).get("summary", "")
    labels = payload.get("issue", {}).get("fields", {}).get("labels", [])
    assignee = (
        payload.get("issue", {})
        .get("fields", {})
        .get("assignee", {})
        .get("displayName", "Unassigned")
    )
    project_key = (
        payload.get("issue", {}).get("fields", {}).get("project", {}).get("key", "")
    )
    component_names = [
        c.get("name", "")
        for c in payload.get("issue", {}).get("fields", {}).get("components", [])
    ]

    label = labels[0] if labels else "backend"
    ruleset_map = {
        "backend": "backend-ruleset.md",
        "frontend": "frontend-ruleset.md",
        "database": "db-ruleset.md",
    }
    ruleset_file = ruleset_map.get(label, "backend-ruleset.md")
    ruleset_path = Path(__file__).parent.parent / "templates" / ruleset_file
    ruleset_content = ruleset_path.read_text(encoding="utf-8") if ruleset_path.exists() else ""

    common_context = (
        f"Issue key: {issue_key}\n"
        f"Summary: {summary}\n"
        f"Labels: {labels}\n"
        f"Assignee: {assignee}\n"
        f"Project: {project_key}\n"
        f"Components: {component_names}\n"
    )

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
            "- If unavailable, do not call Jira read tools and use payload context only.\n"
            "Required output:\n"
            "1) Relevant linked/recent Jira issue summary\n"
            "2) Last 24h main-branch commits related to this issue scope\n"
            "3) Risks/constraints discovered\n"
        ),
        expected_output="A structured context summary with commits, related issues, and constraints.",
        agent=gatherer,
    )

    reason_task = Task(
        description=(
            "From gathered context, generate:\n"
            "1) Personalized AI prompt for the assignee\n"
            f"2) Label-based rules from the ruleset below:\n{ruleset_content}\n"
            "3) Implementation output checklist (code/tests/docs)\n"
            f"{common_context}"
        ),
        expected_output=(
            "Markdown with sections: Prompt, Ruleset, Constraints, Output Format."
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
            "Rules:\n"
            "- Always use issue key from context.\n"
            "- If JIRA_ADD_COMMENT is available, add a comment with a short summary and prompt-ready note.\n"
            "- Only update issue description when JIRA_EDIT_ISSUE is available.\n"
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
    except Exception as exc:
        if "-latest" in model and "NOT_FOUND" in str(exc):
            fallback_model = model.replace("-latest", "")
            gatherer.llm = fallback_model
            reasoner.llm = fallback_model
            propagator.llm = fallback_model
            result = crew.kickoff()
            return CrewRunResult(raw=str(result), model=fallback_model)
        raise

    return CrewRunResult(raw=str(result), model=model)
