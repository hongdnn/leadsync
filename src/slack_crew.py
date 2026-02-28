"""
src/slack_crew.py
Workflow 3: Slack Q&A — Context Retriever -> Tech Lead Reasoner -> Slack Responder.
Exports: run_slack_crew(ticket_key, question, thread_ts, channel_id), parse_slack_text(text)
"""

import logging
import os

from crewai import Agent, Crew, Process, Task

from src.prefs import load_preferences
from src.shared import (
    CrewRunResult,
    _required_env,
    _required_gemini_api_key,
    build_llm,
    build_tools,
)

logger = logging.getLogger(__name__)


def parse_slack_text(text: str) -> tuple[str, str]:
    """
    Split slash command text into ticket key and question.

    Args:
        text: Raw Slack command text, e.g. 'LEADS-123 What is the approach?'.
    Returns:
        Tuple of (ticket_key, question). Question is empty when omitted.
    Side effects:
        None.
    """
    parts = text.strip().split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def run_slack_crew(
    ticket_key: str,
    question: str,
    thread_ts: str | None = None,
    channel_id: str | None = None,
) -> CrewRunResult:
    """
    Run Slack Q&A crew and post answer to Slack.

    Args:
        ticket_key: Jira key like LEADS-123.
        question: Developer question text.
        thread_ts: Optional Slack parent message ts for threaded replies.
        channel_id: Optional override channel id; defaults to SLACK_CHANNEL_ID env var.
    Returns:
        CrewRunResult with raw output and model used.
    Raises:
        RuntimeError: If required environment variables are missing, or if the
            tech lead preferences file (config/tech-lead-context.md) is absent.
        Exception: If kickoff fails and fallback logic also fails.
    Side effects:
        Reads Jira context and posts an answer through Composio Slack tools.
    """
    model = build_llm()
    _required_gemini_api_key()
    composio_user_id = os.getenv("COMPOSIO_USER_ID", "default")
    slack_channel_id = channel_id or _required_env("SLACK_CHANNEL_ID")
    tech_lead_context = load_preferences()

    retriever = Agent(
        role="Context Retriever",
        goal="Fetch Jira context needed to answer the developer question.",
        backstory="You collect concrete ticket facts and comments before reasoning.",
        verbose=True,
        tools=build_tools(user_id=composio_user_id, toolkits=["JIRA"]),
        llm=model,
    )
    reasoner = Agent(
        role="Tech Lead Reasoner",
        goal="Answer from the team's tech lead perspective using project constraints.",
        backstory="You provide direct guidance and cite rules when relevant.",
        verbose=True,
        llm=model,
    )
    responder = Agent(
        role="Slack Responder",
        goal=f"Post the final answer to Slack channel {slack_channel_id}.",
        backstory="You publish concise, actionable responses with clean formatting.",
        verbose=True,
        tools=build_tools(user_id=composio_user_id, toolkits=["SLACK"]),
        llm=model,
    )

    retrieve_task = Task(
        description=(
            f"Fetch Jira ticket {ticket_key}.\n"
            "- Include summary, description, labels, assignee, and comments.\n"
            f"- Developer question: {question}"
        ),
        expected_output="Structured Jira ticket context for downstream reasoning.",
        agent=retriever,
    )
    reason_task = Task(
        description=(
            "Use the ticket context and this tech lead guidance:\n"
            f"---\n{tech_lead_context}\n---\n"
            f"Question: {question}\n"
            "- Return a direct recommendation in 2-4 sentences.\n"
            "- Mention tradeoffs when they matter."
        ),
        expected_output="Opinionated answer that references relevant project constraints.",
        agent=reasoner,
        context=[retrieve_task],
    )
    thread_instruction = (
        f"- Post as a threaded reply using parent ts '{thread_ts}'.\n"
        if thread_ts
        else "- No thread timestamp provided, post as a normal channel message.\n"
    )
    respond_task = Task(
        description=(
            f"Post the answer to Slack channel {slack_channel_id}.\n"
            f"{thread_instruction}"
            f"- Prefix with '[{ticket_key}] Tech Lead says:'."
        ),
        expected_output="Confirmation that Slack message was posted.",
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
        return CrewRunResult(raw=str(result), model=model)
    except Exception as exc:
        logger.exception("Slack crew kickoff failed for model '%s'.", model)
        if "-latest" in model and "NOT_FOUND" in str(exc):
            fallback_model = model.replace("-latest", "")
            logger.warning("Retrying slack crew with fallback model '%s'.", fallback_model)
            retriever.llm = fallback_model
            reasoner.llm = fallback_model
            responder.llm = fallback_model
            retry_result = crew.kickoff()
            return CrewRunResult(raw=str(retry_result), model=fallback_model)
        raise
