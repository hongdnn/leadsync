"""
src/slack_crew.py
Workflow 3: Slack Q&A — Context Retriever -> Solution Reasoner -> Slack Responder.
Exports: run_slack_crew(ticket_key, question, thread_ts, channel_id), parse_slack_text(text)
"""

import logging
import os

from crewai import Agent, Crew, Process, Task

from src.jira_history import build_same_label_progress_context, load_issue_project_and_label
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
            team preferences file (config/tech-lead-context.md) is absent.
        Exception: If kickoff fails and fallback logic also fails.
    Side effects:
        Reads Jira context and posts an answer through Composio Slack tools.
    """
    model = build_llm()
    _required_gemini_api_key()
    composio_user_id = os.getenv("COMPOSIO_USER_ID", "default")
    slack_channel_id = channel_id or _required_env("SLACK_CHANNEL_ID")
    team_preferences = load_preferences()
    jira_tools = build_tools(user_id=composio_user_id, toolkits=["JIRA"])
    project_key, primary_label = load_issue_project_and_label(tools=jira_tools, issue_key=ticket_key)
    same_label_history = build_same_label_progress_context(
        tools=jira_tools,
        project_key=project_key,
        label=primary_label,
        exclude_issue_key=ticket_key,
        limit=10,
    )

    retriever = Agent(
        role="Context Retriever",
        goal="Fetch Jira context needed to answer the developer question.",
        backstory="You collect concrete ticket facts and comments before reasoning.",
        verbose=True,
        tools=jira_tools,
        llm=model,
    )
    reasoner = Agent(
        role="Solution Reasoner",
        goal="Recommend implementation approaches based on ticket context and team guidelines.",
        backstory="You suggest concrete solutions and cite relevant project constraints.",
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
            f"- Developer question: {question}\n"
            "After fetching the ticket, classify the developer question using this rule:\n"
            "  PROGRESS: asks what has already been completed previously for this same label/category,\n"
            "  asks about phase progress, or asks what similar prior tickets already delivered.\n"
            "  IMPLEMENTATION: asks HOW to do something, WHICH approach to take, "
            "SHOULD I use X or Y, HOW TO structure or design something.\n"
            "  GENERAL: asks WHAT the ticket is about, WHO is assigned, WHEN it is due, "
            "status, description, or acceptance criteria.\n"
            "Output the classification as the FIRST line of your response in this exact format:\n"
            "QUESTION_TYPE: PROGRESS\n"
            "or\n"
            "QUESTION_TYPE: IMPLEMENTATION\n"
            "or\n"
            "QUESTION_TYPE: GENERAL\n\n"
            f"Same-label prior progress context:\n{same_label_history}\n"
            f"Current ticket primary label: {primary_label or 'N/A'}"
        ),
        expected_output="QUESTION_TYPE label on the first line, followed by structured Jira ticket context.",
        agent=retriever,
    )
    reason_task = Task(
        description=(
            f"Question: {question}\n\n"
            "Read the QUESTION_TYPE from the retriever output and follow the matching branch:\n\n"
            "If QUESTION_TYPE: PROGRESS\n"
            "- Start with this exact line: 'Here is summary of previous progress related to tasks with the same label:'.\n"
            "- Then provide 3-6 bullets with completed ticket keys and what was completed earlier.\n"
            "- End with one short line: 'What this means now: ...'.\n"
            "- Do NOT include meta/system wording (e.g., 'ticket enriched', 'ready for development').\n\n"
            "If QUESTION_TYPE: GENERAL\n"
            "- Return only factual information from the ticket in 1-2 sentences.\n"
            "- Do NOT reference or apply any tech lead preferences unless question explicitly asks for progress.\n"
            "- Do NOT give implementation opinions.\n\n"
            "If QUESTION_TYPE: IMPLEMENTATION\n"
            "- Apply the following tech lead guidance to give an opinionated recommendation:\n"
            f"---\n{team_preferences}\n---\n"
            "- Return a direct recommendation in 2-4 sentences with one bullet list of key tradeoffs.\n"
            "- Mention tradeoffs when they matter."
        ),
        expected_output=(
            "Either a factual 1-2 sentence answer (GENERAL) or an opinionated "
            "recommendation citing relevant project constraints (IMPLEMENTATION)."
        ),
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
            f"- Prefix with '[{ticket_key}] LeadSync summary:'."
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
