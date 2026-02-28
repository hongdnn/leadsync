"""
src/slack_crew.py
Workflow 3: Slack Q&A — Context Retriever → Tech Lead Reasoner → Slack Responder.
Exports: run_slack_crew(ticket_key, question) -> CrewRunResult, parse_slack_text(text) -> tuple
"""

import os
from pathlib import Path
from typing import Any

from crewai import Agent, Crew, Process, Task

from src.shared import CrewRunResult, _required_env, build_llm, build_tools

TECH_LEAD_CONTEXT_PATH = str(
    Path(__file__).parent.parent / "config" / "tech-lead-context.md"
)


def parse_slack_text(text: str) -> tuple[str, str]:
    """
    Split Slack slash command text into ticket key and question.

    Args:
        text: Raw text field from Slack payload, e.g. 'LEADS-123 What approach?'
    Returns:
        Tuple of (ticket_key, question). Question is empty string if not provided.
    Side effects:
        None.
    """
    parts = text.strip().split(" ", 1)
    ticket_key = parts[0]
    question = parts[1] if len(parts) > 1 else ""
    return ticket_key, question


def _load_tech_lead_context() -> str:
    """
    Load tech lead context config from disk.

    Returns:
        File contents as a string.
    Raises:
        FileNotFoundError: If config/tech-lead-context.md does not exist.
    Side effects:
        Reads from filesystem.
    """
    return Path(TECH_LEAD_CONTEXT_PATH).read_text(encoding="utf-8")


def run_slack_crew(ticket_key: str, question: str) -> CrewRunResult:
    """
    Run the Slack Q&A crew for a given Jira ticket and developer question.

    Args:
        ticket_key: Jira ticket identifier, e.g. 'LEADS-123'.
        question: Developer question text.
    Returns:
        CrewRunResult with the raw Slack reply and model name used.
    Raises:
        RuntimeError: If required env vars are missing.
        Exception: If crew.kickoff() fails and fallback also fails.
    Side effects:
        Posts a Slack message via Composio SLACK tools.
    """
    model = build_llm()
    composio_user_id = os.getenv("COMPOSIO_USER_ID", "default")
    slack_channel_id = _required_env("SLACK_CHANNEL_ID")
    tech_lead_context = _load_tech_lead_context()

    jira_tools = build_tools(user_id=composio_user_id, toolkits=["JIRA"])
    slack_tools = build_tools(user_id=composio_user_id, toolkits=["SLACK"])

    retriever = Agent(
        role="Context Retriever",
        goal="Fetch the full Jira ticket details for the question being asked.",
        backstory=(
            "You pull Jira ticket data so the reasoning agent has accurate context. "
            "Retrieve summary, description, labels, assignee, and comments."
        ),
        verbose=True,
        tools=jira_tools,
        llm=model,
    )

    reasoner = Agent(
        role="Tech Lead Reasoner",
        goal="Answer the developer's question from the tech lead's perspective.",
        backstory=(
            "You reason like an experienced tech lead using defined preferences and "
            "non-negotiables. You give direct, opinionated answers — not ticket summaries."
        ),
        verbose=True,
        llm=model,
    )

    responder = Agent(
        role="Slack Responder",
        goal=f"Post the reasoned answer to Slack channel {slack_channel_id}.",
        backstory=(
            "You post the tech lead's answer to Slack as a well-formatted message. "
            "Keep it concise, actionable, and start with the ticket key."
        ),
        verbose=True,
        tools=slack_tools,
        llm=model,
    )

    retrieve_task = Task(
        description=(
            f"Fetch Jira ticket {ticket_key} using JIRA tools.\n"
            "Retrieve: summary, description, labels, assignee, any comments.\n"
            f"Developer question: {question}"
        ),
        expected_output="Structured ticket context: summary, description, labels, assignee.",
        agent=retriever,
    )

    reason_task = Task(
        description=(
            "Using the retrieved ticket context and this tech lead configuration:\n"
            f"---\n{tech_lead_context}\n---\n"
            f"Answer this question: {question}\n"
            "- Apply the tech lead's preferences and per-label rules.\n"
            "- Give a direct, opinionated answer (not a ticket summary).\n"
            "- Reference specific rules from the config when relevant."
        ),
        expected_output=(
            "A direct, opinionated answer of 2-4 sentences referencing specific tech lead rules."
        ),
        agent=reasoner,
        context=[retrieve_task],
    )

    respond_task = Task(
        description=(
            f"Post the reasoned answer to Slack channel {slack_channel_id}.\n"
            "- Use SLACK tools to post the message.\n"
            f"- Format: Start with '[{ticket_key}] Tech Lead says:' then the answer.\n"
            "- Keep under 400 characters for readability."
        ),
        expected_output="Confirmation that the Slack message was posted successfully.",
        agent=responder,
        context=[reason_task],
    )

    crew = Crew(
        agents=[retriever, reasoner, responder],
        tasks=[retrieve_task, reason_task, respond_task],
        process=Process.sequential,
        verbose=True,
    )

    try:
        result = crew.kickoff()
    except Exception as exc:
        if "-latest" in model and "NOT_FOUND" in str(exc):
            fallback_model = model.replace("-latest", "")
            retriever.llm = fallback_model
            reasoner.llm = fallback_model
            responder.llm = fallback_model
            result = crew.kickoff()
            return CrewRunResult(raw=str(result), model=fallback_model)
        raise

    return CrewRunResult(raw=str(result), model=model)
