"""Workflow 3 crew assembly helpers."""

from typing import Any

from src.stream import stream_enabled


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
        backstory=(
            "You give specific, actionable engineering guidance. "
            "You always structure your output with clear labeled sections so it can be formatted for Slack."
        ),
        verbose=True,
        llm=model,
    )
    responder = runtime.Agent(
        role="Slack Responder",
        goal=f"Post the final answer to Slack channel {slack_channel_id} with clean Slack formatting.",
        backstory=(
            "You format engineering answers for Slack using mrkdwn. "
            "You use *bold* for headers, bullet lists for details, and keep messages scannable."
        ),
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
            "- Output section PROGRESS SUMMARY:\n"
            "  Start with this exact line: 'Here is summary of previous progress related to tasks with the same label:'.\n"
            "  Then provide 3-6 bullets, each starting with the ticket key and what was completed.\n"
            "- Output section CURRENT IMPACT:\n"
            "  One sentence: what this prior work means for the current ticket.\n"
            "- Do NOT include meta/system wording (e.g., 'ticket enriched', 'ready for development').\n\n"
            "If QUESTION_TYPE: GENERAL\n"
            "- Output section ANSWER:\n"
            "  Return only factual information from the ticket in 1-3 sentences.\n"
            "  Include relevant details: assignee, status, priority, labels, or due date if available.\n"
            "- Do NOT reference or apply any tech lead preferences unless question explicitly asks for progress.\n"
            "- Do NOT give implementation opinions.\n\n"
            "If QUESTION_TYPE: IMPLEMENTATION\n"
            "- Apply the following tech lead guidance to give an opinionated recommendation:\n"
            f"- Category: {preference_category}\n---\n{team_preferences}\n---\n"
            "- Output section RECOMMENDATION:\n"
            "  2-4 sentences with specific, actionable guidance. Mention concrete technologies,\n"
            "  patterns, or file areas. Never be vague or generic.\n"
            "- Output section TRADEOFFS:\n"
            "  2-4 bullet points, each a short sentence about a key tradeoff or risk.\n"
            "- Output section NEXT STEPS:\n"
            "  2-4 numbered steps the developer should take next.\n\n"
            "IMPORTANT: Always output section labels (RECOMMENDATION:, TRADEOFFS:, etc.) on their own line."
        ),
        expected_output=(
            "Structured answer with labeled sections: "
            "RECOMMENDATION/TRADEOFFS/NEXT STEPS for IMPLEMENTATION, "
            "PROGRESS SUMMARY/CURRENT IMPACT for PROGRESS, "
            "or ANSWER for GENERAL."
        ),
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
            f"Post the answer to Slack channel {slack_channel_id} using SLACK tools.\n"
            f"{thread_instruction}\n"
            "Format the message using Slack mrkdwn as follows:\n\n"
            f"Line 1: *[{ticket_key}] LeadSync*\n"
            "Line 2: blank line\n\n"
            "Then format the reasoner output based on which sections are present:\n\n"
            "If RECOMMENDATION section exists (IMPLEMENTATION question):\n"
            "- *Recommendation*\n"
            "- The recommendation text on the next line\n"
            "- Blank line\n"
            "- *Key Tradeoffs*\n"
            "- Each tradeoff as a bullet point line\n"
            "- Blank line\n"
            "- *Next Steps*\n"
            "- Each step as a numbered line\n\n"
            "If PROGRESS SUMMARY section exists (PROGRESS question):\n"
            "- *Previous Progress*\n"
            "- Each completed ticket as a bullet point line\n"
            "- Blank line\n"
            "- The CURRENT IMPACT text in italics using _text_\n\n"
            "If ANSWER section exists (GENERAL question):\n"
            "- Just the answer text directly after the header\n\n"
            "Rules:\n"
            "- Use *bold* for section headers only.\n"
            "- Do NOT add any commentary, preamble, or sign-off beyond what the reasoner produced.\n"
            "- Keep the message compact and scannable."
        ),
        expected_output="Confirmation that the formatted Slack message was posted.",
        agent=responder,
        context=[reason_task],
    )
    crew = runtime.Crew(
        agents=[retriever, reasoner, responder],
        tasks=[retrieve_task, reason_task, respond_task],
        process=runtime.Process.sequential,
        verbose=True,
        stream=stream_enabled(),
    )
    return retrieve_task, reason_task, respond_task, [retriever, reasoner, responder], crew
