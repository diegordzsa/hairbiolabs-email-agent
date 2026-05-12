# Hair Biolabs Email Agent

AI-powered customer service agent for [Hair Biolabs](https://hairbiolabs.com). Monitors Reamaze conversations, classifies them with Claude AI, enriches with Shopify customer data, and generates draft responses for human review.

## How It Works

```
Reamaze (new conversations) -> Classify (Claude Haiku) -> Shopify lookup -> Generate reply (Claude Sonnet) -> Internal note (draft) -> Slack notification
```

1. Every 5 minutes, fetches unresolved Reamaze conversations from real customers
2. Classifies each with Claude Haiku (order status, product question, return/refund, complaint, legal, spam)
3. Routes: legal -> tag + Slack alert (no draft). Spam -> tag + skip.
4. Looks up customer in Shopify for order context
5. Generates a response draft with Claude Sonnet using company policies
6. Creates an **internal note** in Reamaze (not visible to customer) with the draft
7. Tags the conversation as `ai-processed`
8. Notifies the team on Slack with a link to review

**All drafts require human review before sending.** The agent never sends messages to customers.

## Setup

### Prerequisites
- Python 3.12+
- Reamaze account with API access
- Shopify store with client credentials app
- Anthropic API key
- Slack incoming webhook

### Installation

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with your credentials
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `REAMAZE_BRAND` | Reamaze subdomain (e.g., `hairbiolabs`) |
| `REAMAZE_LOGIN_EMAIL` | Staff email for API auth |
| `REAMAZE_API_TOKEN` | Reamaze API token |
| `SHOPIFY_STORE_DOMAIN` | Shopify store domain |
| `SHOPIFY_CLIENT_ID` | Shopify app client ID |
| `SHOPIFY_CLIENT_SECRET` | Shopify app client secret |
| `ANTHROPIC_API_KEY` | Claude API key |
| `SLACK_WEBHOOK_URL` | Slack webhook URL |
| `TIMEZONE` | Default: `America/Mexico_City` |
| `DRY_RUN` | Set to `true` to skip note creation |

### Run Locally

```bash
# Dry run (no notes created, no tags applied in production)
DRY_RUN=true python -m src.main

# Production run
python -m src.main
```

### Deploy

The agent runs via GitHub Actions every 5 minutes. Add all environment variables as repository secrets in GitHub.

## Architecture

| Module | Purpose |
|--------|---------|
| `src/config.py` | Environment variables and validation |
| `src/reamaze_client.py` | Reamaze API: conversations, notes, tags |
| `src/shopify_client.py` | Shopify customer and order lookup |
| `src/claude_client.py` | AI classification and response generation |
| `src/slack_client.py` | Team notifications |
| `src/main.py` | Orchestration and retry logic |
| `policies/hair_biolabs.md` | Company policies for AI prompts |
