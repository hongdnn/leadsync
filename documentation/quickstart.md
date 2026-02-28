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
LEADSYNC_FRONTEND_PREFS_DOC_ID=...
LEADSYNC_BACKEND_PREFS_DOC_ID=...
LEADSYNC_DATABASE_PREFS_DOC_ID=...
LEADSYNC_MEMORY_ENABLED=true
LEADSYNC_MEMORY_DB_PATH=data/leadsync.db
LEADSYNC_DIGEST_WINDOW_MINUTES=60
LEADSYNC_DIGEST_IDEMPOTENCY_ENABLED=true
LEADSYNC_GITHUB_REPO_OWNER=...
LEADSYNC_GITHUB_REPO_NAME=...
# Optional but recommended in deploy:
# LEADSYNC_TRIGGER_TOKEN=replace_with_shared_secret
```
Google Docs IDs come from URLs like:
`https://docs.google.com/document/d/<DOCUMENT_ID>/edit`.
Ensure the connected Composio account can read all three preference documents.
Workflow 1 Jira enrichment also requires GitHub repo targeting via
`LEADSYNC_GITHUB_REPO_OWNER` and `LEADSYNC_GITHUB_REPO_NAME` to produce `## Key Files`.

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

Scheduled-style call with explicit window metadata:

```bash
curl -X POST http://127.0.0.1:8000/digest/trigger \
  -H "Content-Type: application/json" \
  -H "X-LeadSync-Trigger-Token: $LEADSYNC_TRIGGER_TOKEN" \
  -d '{"run_source":"scheduled","window_minutes":60,"bucket_start_utc":"2026-02-28T11:00:00Z","repo_owner":"your-org","repo_name":"your-repo"}'
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

## 5. Railway Hourly Scheduler (Hackathon)

1. Create a dedicated Slack channel for digest output (example: `#leadsync-hourly-digest`).
2. Invite your LeadSync Slack bot/app to that channel.
3. Copy the channel ID (`C...`) and set it as `SLACK_CHANNEL_ID` in the API service.
4. Deploy the API service normally (the one running `uvicorn src.main:app`).
5. Set `LEADSYNC_TRIGGER_TOKEN` in the API service env vars.
6. Create a Railway Cron service from the same repo.
7. In the Cron service, set:
   - `DIGEST_TRIGGER_URL=https://<your-api-domain>/digest/trigger`
   - `LEADSYNC_TRIGGER_TOKEN=<same-shared-secret>`
   - `LEADSYNC_GITHUB_REPO_OWNER=<your-org-or-username>`
   - `LEADSYNC_GITHUB_REPO_NAME=<your-repo-name>`
8. Set schedule expression to hourly UTC (recommended offset): `7 * * * *`.
9. Cron command example:

```bash
python -c "import json, os, urllib.request; req=urllib.request.Request(os.environ['DIGEST_TRIGGER_URL'], data=json.dumps({'run_source':'scheduled','window_minutes':60,'repo_owner':os.environ['LEADSYNC_GITHUB_REPO_OWNER'],'repo_name':os.environ['LEADSYNC_GITHUB_REPO_NAME']}).encode('utf-8'), headers={'Content-Type':'application/json','X-LeadSync-Trigger-Token':os.environ['LEADSYNC_TRIGGER_TOKEN']}, method='POST'); print(urllib.request.urlopen(req, timeout=60).read().decode())"
```

10. Trigger once manually for verification:

```bash
curl -X POST https://<your-api-domain>/digest/trigger \
  -H "Content-Type: application/json" \
  -H "X-LeadSync-Trigger-Token: <same-shared-secret>" \
  -d '{"run_source":"manual","window_minutes":60,"repo_owner":"your-org","repo_name":"your-repo"}'
```

Expected: one message appears in the dedicated Slack channel each run, including quiet hours (no meaningful commits).
