"""Workflow 3 crew assembly helpers."""

from typing import Any


def build_workflow3_crew(
    *,
    runtime: Any,
    model: str,
    ticket_key: str,
    question: str,
    thread_ts: str | None,
    slack_channel_id: str,
    jira_tools: list[Any],
    slack_tools: list[Any],
    same_label_history: str,
    memory_context: str,
    primary_label: str,
    preference_category: str,
    team_preferences: str,
) -> tuple[Any, Any, Any, list[Any], Any]:
    """Assemble workflow3 agents/tasks/crew objects."""
    retriever = runtime.Agent(
        role="Context Retriever",
        goal="Fetch Jira context needed to answer the developer question.",
        backstory="You collect concrete ticket facts and comments before reasoning.",
        verbose=True,
        tools=jira_tools,
        llm=model,
    )
    reasoner = runtime.Agent(
        role="Solution Reasoner",
        goal="Recommend implementation approaches based on ticket context and team guidelines.",
        backstory="You suggest concrete solutions and cite relevant project constraints.",
        verbose=True,
        llm=model,
    )
    responder = runtime.Agent(
        role="Slack Responder",
        goal=f"Post the final answer to Slack channel {slack_channel_id}.",
        backstory="You publish concise, actionable responses with clean formatting.",
        verbose=True,
        tools=slack_tools,
        llm=model,
    )
    retrieve_task = runtime.Task(
        description=(
            f"Fetch Jira ticket {ticket_key}.\n"
            "- Include summary, description, labels, assignee, and comments.\n"
            f"- Developer question: {question}\n"
            "After fetching the ticket, classify the developer question using this rule:\n"
            "  PROGRESS: asks what has already been completed previously for this same label/category,\n"
            "  asks about phase progress, or asks what similar prior tickets already delivered.\n"
            "  IMPLEMENTATION: asks HOW to do something, WHICH approach to take, SHOULD I use X or Y.\n"
            "  GENERAL: asks WHAT the ticket is about, WHO is assigned, due/status/description details.\n"
            "Output the classification as the FIRST line exactly as QUESTION_TYPE: PROGRESS,\n"
            "QUESTION_TYPE: IMPLEMENTATION, or QUESTION_TYPE: GENERAL.\n\n"
            f"Same-label prior progress context:\n{same_label_history}\n"
            f"Stored workflow memory context:\n{memory_context}\n"
            "- Use memory context to reference prior decisions and previous Q&A when relevant.\n"
            f"Current ticket primary label: {primary_label or 'N/A'}"
        ),
        expected_output="QUESTION_TYPE label on first line, followed by structured Jira ticket context.",
        agent=retriever,
    )
    reason_task = runtime.Task(
        description=(
            f"Question: {question}\n\n"
            "Read QUESTION_TYPE from retriever output and follow matching branch:\n\n"
            "If QUESTION_TYPE: PROGRESS\n"
            "- Start with this exact line: 'Here is summary of previous progress related to tasks with the same label:'.\n"
            "- Provide 3-6 bullets with completed ticket keys and what was completed earlier.\n"
            "- End with one short line: 'What this means now: ...'.\n"
            "- Do NOT include meta/system wording (e.g., 'ticket enriched', 'ready for development').\n\n"
            "If QUESTION_TYPE: GENERAL\n"
            "- Return only factual information from the ticket in 1-2 sentences.\n"
            "- Do NOT reference or apply any tech lead preferences unless question explicitly asks for progress.\n"
            "- Do NOT give implementation opinions.\n\n"
            "If QUESTION_TYPE: IMPLEMENTATION\n"
            "- Apply the following tech lead guidance to give an opinionated recommendation:\n"
            f"- Category: {preference_category}\n---\n{team_preferences}\n---\n"
            "- Return direct recommendation in 2-4 sentences with one bullet list of key tradeoffs.\n"
            "- Mention tradeoffs when they matter."
        ),
        expected_output="Factual answer for GENERAL or opinionated guidance for IMPLEMENTATION/PROGRESS.",
        agent=reasoner,
        context=[retrieve_task],
    )
    thread_instruction = (
        f"- Post as a threaded reply using parent ts '{thread_ts}'.\n"
        if thread_ts
        else "- No thread timestamp provided, post as a normal channel message.\n"
    )
    respond_task = runtime.Task(
        description=(
            f"Post the answer to Slack channel {slack_channel_id}.\n"
            f"{thread_instruction}- Prefix with '[{ticket_key}] LeadSync summary:'."
        ),
        expected_output="Confirmation that Slack message was posted.",
        agent=responder,
        context=[reason_task],
    )
    crew = runtime.Crew(
        agents=[retriever, reasoner, responder],
        tasks=[retrieve_task, reason_task, respond_task],
        process=runtime.Process.sequential,
        verbose=True,
    )
    return retrieve_task, reason_task, respond_task, [retriever, reasoner, responder], crew
