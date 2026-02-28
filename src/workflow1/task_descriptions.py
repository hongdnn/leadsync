"""Workflow 1 task description builders."""


def gather_description(
    *,
    common_context: str,
    tool_names: list[str],
    has_jira_get_issue: bool,
    has_github_tools: bool,
    repo_owner: str,
    repo_name: str,
) -> str:
    """Build gatherer task prompt text."""
    return (
        "Gather context for this issue.\n"
        f"{common_context}\n"
        f"Available tool names: {tool_names}\n"
        "Rules:\n"
        f"- JIRA_GET_ISSUE available: {has_jira_get_issue}\n"
        f"- Any GITHUB_* tools available: {has_github_tools}\n"
        f"- GitHub repository target: {repo_owner}/{repo_name}\n"
        "- Use GitHub tools to search code/files relevant to summary, description, labels, and components.\n"
        "- Include recent commits as supporting signal only.\n"
        "Required output:\n"
        "1) Relevant linked/recent Jira issue summary\n"
        "2) Last 24h main-branch commits related to this issue scope (if found)\n"
        "3) Risks/constraints discovered\n"
        "4) Summary of previous progress from the latest 10 completed same-label tickets\n"
        "5) 3-8 source files or modules likely impacted as strict lines in this exact format:\n"
        "   KEY_FILE: <path> | WHY: <one-line rationale> | CONFIDENCE: <high|medium|low>\n"
    )


def reason_description(
    *,
    ruleset_file: str,
    ruleset_content: str,
    preference_category: str,
    team_preferences: str,
    common_context: str,
    general_rules: str = "",
) -> str:
    """Build reasoner task prompt text."""
    general_rules_block = ""
    if general_rules:
        general_rules_block = (
            f"Apply these general leader rules to ALL tickets:\n{general_rules}\n"
        )
    return (
        "From gathered context, generate:\n"
        "1) One markdown document with these exact sections in order:\n"
        "   - ## Task\n"
        "   - ## Context\n"
        "   - ## Key Files\n"
        "   - ## Constraints\n"
        "   - ## Implementation Rules\n"
        "   - ## Expected Output\n"
        "2) In the Context section, include a concise summary of previous same-label completed "
        "work so the assignee sees what has already been completed in this development phase.\n"
        "3) In the Key Files section, include exactly the key files from gatherer output with path, why, and confidence.\n"
        f"{general_rules_block}"
        f"4) Apply rules from selected ruleset '{ruleset_file}':\n{ruleset_content}\n"
        f"5) Apply team preference guidance from Google Docs category '{preference_category}':\n"
        f"{team_preferences}\n"
        "6) Add implementation output checklist (code/tests/docs)\n"
        "7) Keep tone technical and execution-oriented. Avoid broad ticket summaries.\n"
        f"{common_context}"
    )


def propagate_description(*, tool_names: list[str], has_comment: bool, has_edit: bool, has_attach: bool) -> str:
    """Build propagator task prompt text."""
    return (
        "Write back to Jira:\n"
        f"Available tool names: {tool_names}\n"
        f"- JIRA_ADD_COMMENT available: {has_comment}\n"
        f"- JIRA_EDIT_ISSUE available: {has_edit}\n"
        f"- JIRA_ADD_ATTACHMENT available: {has_attach}\n"
        "Rules:\n"
        "- Always use issue key from context.\n"
        "- If JIRA_ADD_COMMENT is available, add plain-text technical execution guidance without markdown syntax.\n"
        "- Comment structure (plain text, no '#', no bullet markers):\n"
        "  1) One line: 'Previous same-label progress:'\n"
        "  2) 3-5 short lines of completed technical work from recent same-label tickets.\n"
        "  3) One line: 'Recommended implementation path for current task:'\n"
        "  4) 3-5 short lines: concrete steps, likely files/modules, validation checks.\n"
        "- Only update issue description when JIRA_EDIT_ISSUE is available.\n"
        "- For issue description updates, write technical execution guidance (approach, code areas, risks, test plan) "
        "instead of a generic summary.\n"
        "- For issue description updates, avoid opening like 'This ticket ...' or 'This task ...'.\n"
        "- Mention that a prompt markdown attachment will be added when available.\n"
        "- Do NOT write meta/system statements such as 'the ticket has been enriched' or "
        "'it is now ready for development'. Keep wording developer-facing and concrete.\n"
        "- Never call any tool that is not listed in available tool names."
    )
