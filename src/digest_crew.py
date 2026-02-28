"""
src/digest_crew.py
Workflow 2: End-of-Day Digest — GitHub Scanner -> Digest Writer -> Slack Poster.
Exports: run_digest_crew() -> CrewRunResult
"""

import logging
import os

from crewai import Agent, Crew, Process, Task

from src.shared import (
    CrewRunResult,
    _required_env,
    _required_gemini_api_key,
    build_llm,
    build_tools,
)

logger = logging.getLogger(__name__)


def run_digest_crew() -> CrewRunResult:
    """
    Run the end-of-day digest crew and post summary to Slack.

    Returns:
        CrewRunResult with raw crew output and model used.
    Raises:
        RuntimeError: If required environment variables are missing.
        Exception: If kickoff fails and fallback logic also fails.
    Side effects:
        Reads GitHub context and posts a summary message to Slack via Composio tools.
    """
    model = build_llm()
    _required_gemini_api_key()
    composio_user_id = os.getenv("COMPOSIO_USER_ID", "default")
    slack_channel_id = _required_env("SLACK_CHANNEL_ID")

    github_tools = build_tools(user_id=composio_user_id, toolkits=["GITHUB"])
    slack_tools = build_tools(user_id=composio_user_id, toolkits=["SLACK"])

    scanner = Agent(
        role="GitHub Scanner",
        goal="Collect meaningful main-branch commit activity from the last 24 hours.",
        backstory="You gather commit signals only and avoid speculation.",
        verbose=True,
        tools=github_tools,
        llm=model,
    )
    writer = Agent(
        role="Digest Writer",
        goal="Group the scanned work by area and produce a concise team digest.",
        backstory="You write clear summaries for engineers and avoid generic filler.",
        verbose=True,
        llm=model,
    )
    poster = Agent(
        role="Slack Poster",
        goal=f"Post the digest to Slack channel {slack_channel_id}.",
        backstory="You publish the final digest message exactly once with clear formatting.",
        verbose=True,
        tools=slack_tools,
        llm=model,
    )

    scan_task = Task(
        description=(
            "Use GITHUB tools to scan main-branch changes from the last 24 hours.\n"
            "- Include author, commit summary, impacted area, and risk flags.\n"
            "- Exclude noise-only commits when possible."
        ),
        expected_output="Structured list of meaningful commits grouped by area.",
        agent=scanner,
    )
    write_task = Task(
        description=(
            "Draft a concise daily digest from scanned commits.\n"
            "- Group by subsystem.\n"
            "- Mention key risks and follow-ups.\n"
            "- Keep under 12 lines."
        ),
        expected_output="A polished plain-text daily digest message.",
        agent=writer,
        context=[scan_task],
    )
    post_task = Task(
        description=(
            f"Post the digest to Slack channel {slack_channel_id} using SLACK tools.\n"
            "- Prefix with '[LeadSync Daily Digest]'.\n"
            "- Preserve line breaks for readability."
        ),
        expected_output="Confirmation that the digest was posted to Slack.",
        agent=poster,
        context=[write_task],
    )

    crew = Crew(
        agents=[scanner, writer, poster],
        tasks=[scan_task, write_task, post_task],
        process=Process.sequential,
        verbose=True,
    )
    try:
        result = crew.kickoff()
        return CrewRunResult(raw=str(result), model=model)
    except Exception as exc:
        logger.exception("Digest crew kickoff failed for model '%s'.", model)
        if "-latest" in model and "NOT_FOUND" in str(exc):
            fallback_model = model.replace("-latest", "")
            logger.warning("Retrying digest crew with fallback model '%s'.", fallback_model)
            scanner.llm = fallback_model
            writer.llm = fallback_model
            poster.llm = fallback_model
            retry_result = crew.kickoff()
            return CrewRunResult(raw=str(retry_result), model=fallback_model)
        raise
