# LeadSync Quickstart Guide

This guide covers local setup and endpoint testing for all three LeadSync workflows.

## 1. Prerequisites

- Python 3.11+
- Composio API key
- Gemini API key
- Slack channel id

## 2. Environment Setup

Create `.env` from `.env.example` and set:

```env
COMPOSIO_API_KEY=...
COMPOSIO_USER_ID=default
GEMINI_API_KEY=...
# Optional legacy alias still supported:
# GOOGLE_API_KEY=...
LEADSYNC_GEMINI_MODEL=gemini/gemini-2.5-flash
SLACK_CHANNEL_ID=...
```

## 3. Run the API

```bash
uvicorn src.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## 4. Test Endpoints

### Workflow 1: Jira Enrichment

```bash
curl -X POST http://127.0.0.1:8000/webhooks/jira \
  -H "Content-Type: application/json" \
  -d '{"issue":{"key":"LEADS-1","fields":{"summary":"Add rate limiting","labels":["backend"]}}}'
```

### Workflow 2: Daily Digest

```bash
curl -X POST http://127.0.0.1:8000/digest/trigger
```

### Workflow 3: Slack Q&A

JSON test:

```bash
curl -X POST http://127.0.0.1:8000/slack/commands \
  -H "Content-Type: application/json" \
  -d '{"ticket_key":"LEADS-1","question":"Should I extend the users table?","thread_ts":"1711111.1"}'
```

Slash-command style form test:

```bash
curl -X POST http://127.0.0.1:8000/slack/commands \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "text=LEADS-1 Should I extend the users table?" \
  --data-urlencode "channel_id=C12345678"
```
