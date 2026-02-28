"""
Workflow 6 crew assembly helpers.
Exports: build_done_scan_crew
"""

from typing import Any

from src.workflow6.task_descriptions import scan_description, summarize_description


def build_done_scan_crew(
    *,
    runtime: Any,
    model: str,
    github_tools: list[Any],
    issue_key: str,
    summary: str,
    description: str,
    repo_owner: str,
    repo_name: str,
) -> tuple[Any, Any, list[Any], Any]:
    """Assemble Workflow 6 agents, tasks, and crew.

    Args:
        runtime: Object providing Agent, Task, Crew, Process constructors.
        model: LLM model name.
        github_tools: Composio GitHub tools for the scanner agent.
        issue_key: Jira issue key.
        summary: Ticket summary text.
        description: Ticket description text.
        repo_owner: GitHub repository owner.
        repo_name: GitHub repository name.
    Returns:
        Tuple of (scan_task, summarize_task, agents_list, crew).
    """
    scanner = runtime.Agent(
        role="Implementation Scanner",
        goal="Find commits and PRs on main that implemented this ticket.",
        backstory="You search GitHub commit history and merged PRs for code changes.",
        verbose=True,
        tools=github_tools,
        llm=model,
    )
    summarizer = runtime.Agent(
        role="Implementation Summarizer",
        goal="Create a concise summary of how this ticket was implemented in code.",
        backstory="You distill code change findings into clear implementation summaries.",
        verbose=True,
        tools=[],
        llm=model,
    )

    scan_task = runtime.Task(
        description=scan_description(
            issue_key=issue_key,
            summary=summary,
            description=description,
            repo_owner=repo_owner,
            repo_name=repo_name,
        ),
        expected_output="List of commits and PRs with files changed, or NO_MATCHES_FOUND.",
        agent=scanner,
    )
    summarize_task = runtime.Task(
        description=summarize_description(issue_key=issue_key, summary=summary),
        expected_output="IMPLEMENTATION_SUMMARY and FILES_CHANGED lines.",
        agent=summarizer,
        context=[scan_task],
    )

    agents = [scanner, summarizer]
    crew = runtime.Crew(
        agents=agents,
        tasks=[scan_task, summarize_task],
        process=runtime.Process.sequential,
        verbose=True,
    )
    return scan_task, summarize_task, agents, crew
