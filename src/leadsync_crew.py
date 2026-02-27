import os
from dataclasses import dataclass
from typing import Any

from crewai import Agent, Crew, Process, Task


DEFAULT_GEMINI_MODEL = "gemini/gemini-2.5-flash"


@dataclass
class CrewRunResult:
    raw: str
    model: str


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _build_tools(user_id: str) -> list[Any]:
    _required_env("COMPOSIO_API_KEY")
    os.environ.setdefault("COMPOSIO_CACHE_DIR", ".composio-cache")
    from composio import Composio
    from composio_crewai import CrewAIProvider

    composio = Composio(provider=CrewAIProvider())
    return composio.tools.get(user_id=user_id, toolkits=["JIRA", "GITHUB"])


def run_leadsync_crew(payload: dict[str, Any]) -> CrewRunResult:
    # gemini_api_key = _required_env("GEMINI_API_KEY")
    # os.environ.setdefault("GOOGLE_API_KEY", gemini_api_key)
    model = os.getenv("LEADSYNC_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    composio_user_id = os.getenv("COMPOSIO_USER_ID", "default")
    tools = _build_tools(user_id=composio_user_id)

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
        tools=tools,
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
            "Use Jira and GitHub tools to gather context for this issue.\n"
            f"{common_context}\n"
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
            "2) Label-based rules snippet (backend/frontend/database fallback)\n"
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
            "1) Update issue description with a short AI Context section\n"
            "2) Add a comment that prompt/rules are ready\n"
            "Issue key must be used from context."
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
