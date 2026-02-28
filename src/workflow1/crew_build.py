"""Workflow 1 crew assembly helpers."""

from typing import Any

from src.workflow1.task_descriptions import (
    gather_description,
    propagate_description,
    reason_description,
)


def build_workflow1_crew(
    *,
    runtime: Any,
    model: str,
    tools: list[Any],
    tool_names: set[str],
    context_text: str,
    ruleset_file: str,
    ruleset_content: str,
    preference_category: str,
    team_preferences: str,
    has_jira_get_issue: bool,
    has_jira_edit_issue: bool,
    has_jira_add_comment: bool,
    has_jira_add_attachment: bool,
    has_github_tools: bool,
    repo_owner: str,
    repo_name: str,
    general_rules: str = "",
) -> tuple[Any, Any, Any, list[Any], Any]:
    """Assemble workflow1 agents/tasks/crew objects."""
    gatherer = runtime.Agent(
        role="Context Gatherer",
        goal="Collect Jira and GitHub context needed to implement the issue correctly.",
        backstory="You are responsible for finding relevant context from Jira and recent commits.",
        verbose=True,
        tools=tools,
        llm=model,
    )
    reasoner = runtime.Agent(
        role="Intent Reasoner",
        goal="Create a personalized implementation prompt based on ticket labels and context.",
        backstory="You map labels to rulesets and produce a copy-paste-ready engineering prompt.",
        verbose=True,
        llm=model,
    )
    propagator = runtime.Agent(
        role="Propagator",
        goal="Write the generated context and instructions back to the Jira issue.",
        backstory="You update Jira description/comments with technical execution guidance.",
        verbose=True,
        tools=tools,
        llm=model,
    )
    gather_task = runtime.Task(
        description=gather_description(
            common_context=context_text,
            tool_names=sorted(tool_names),
            has_jira_get_issue=has_jira_get_issue,
            has_github_tools=has_github_tools,
            repo_owner=repo_owner,
            repo_name=repo_name,
        ),
        expected_output="A structured context summary with commits, related issues, and constraints.",
        agent=gatherer,
    )
    reason_task = runtime.Task(
        description=reason_description(
            ruleset_file=ruleset_file,
            ruleset_content=ruleset_content,
            preference_category=preference_category,
            team_preferences=team_preferences,
            common_context=context_text,
            general_rules=general_rules,
        ),
        expected_output="Markdown containing exactly the five required sections for prompt-[ticket-key].md.",
        agent=reasoner,
        context=[gather_task],
    )
    propagate_task = runtime.Task(
        description=propagate_description(
            tool_names=sorted(tool_names),
            has_comment=has_jira_add_comment,
            has_edit=has_jira_edit_issue,
            has_attach=has_jira_add_attachment,
        ),
        expected_output="Confirmation of Jira write-back actions taken.",
        agent=propagator,
        context=[reason_task],
    )
    crew = runtime.Crew(
        agents=[gatherer, reasoner, propagator],
        tasks=[gather_task, reason_task, propagate_task],
        process=runtime.Process.sequential,
        verbose=True,
    )
    return gather_task, reason_task, propagate_task, [gatherer, reasoner, propagator], crew
