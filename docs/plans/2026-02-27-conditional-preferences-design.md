# Conditional Preference Injection — Design

**Date:** 2026-02-27
**Status:** Approved

---

## Problem

Tech lead preferences are injected into every Slack Q&A response regardless of the question type. A developer asking "who is assigned to this ticket?" receives a response influenced by architectural rules and coding constraints — preferences that are irrelevant to a factual question.

---

## Goal

Inject tech lead preferences **only** when the developer's question asks HOW to implement something. General/factual questions get a brief, ticket-only answer with no tech lead opinion.

---

## Classification Rule

**IMPLEMENTATION** — the question asks how to do something, which approach to take, whether to use X or Y, how to structure/design something.

Examples:
- "Should I extend the table or create a new one?"
- "How should I implement rate limiting here?"
- "Which approach for caching?"

**GENERAL** — the question asks what, who, when, status, or description.

Examples:
- "What is this ticket about?"
- "Who is assigned?"
- "What's the acceptance criteria?"

---

## Architecture

No new files. No new agents. One file changed: `src/slack_crew.py`.

### Change 1: `retrieve_task` description

Add classification instructions at the end of the existing retrieve task:

```
After fetching ticket context, classify the developer's question using this rule:
- IMPLEMENTATION: asks HOW to do something, WHICH approach, SHOULD I use X or Y, HOW TO structure/design.
- GENERAL: asks WHAT the ticket is, WHO is assigned, WHEN it's due, status, description, criteria.

Output a clear label on the FIRST line of your response:
QUESTION_TYPE: IMPLEMENTATION
or
QUESTION_TYPE: GENERAL
```

### Change 2: `reason_task` description

Replace the flat "use tech lead guidance" block with a conditional branch:

```
Read the QUESTION_TYPE label from the retriever output:

If QUESTION_TYPE: GENERAL
- Return only factual information from the ticket in 1-2 sentences.
- Do NOT reference or apply any tech lead preferences.
- Do NOT give implementation opinions.

If QUESTION_TYPE: IMPLEMENTATION
- Apply the following tech lead guidance to give an opinionated recommendation:
---
{tech_lead_context}
---
- Return a direct recommendation in 2-4 sentences.
- Mention tradeoffs when they matter.
```

---

## Data Flow

```
"/leadsync LEADS-42 Should I extend the users table?"

  Retriever → QUESTION_TYPE: IMPLEMENTATION + ticket facts
  Reasoner  → applies preferences → opinionated answer
  Responder → posts to Slack

"/leadsync LEADS-42 Who is assigned to this?"

  Retriever → QUESTION_TYPE: GENERAL + ticket facts
  Reasoner  → ignores preferences → "Alice is assigned to LEADS-42."
  Responder → posts to Slack
```

---

## Scope

- **In scope:** Modify `retrieve_task` and `reason_task` descriptions in `slack_crew.py`
- **Out of scope:** Changes to `prefs.py`, `main.py`, any other crew file

---

## Test Plan

Update `tests/test_slack_crew.py`:
- Existing tests: verify they still pass (no behavioral regression on happy path)
- The mock patches `load_preferences` return value — still valid
- No new test structure needed: the AI classification is prompt-level behavior, not Python logic

No new unit tests are strictly required — the change is in agent prompt text. The existing crew kickoff mock tests confirm the wiring still works.
