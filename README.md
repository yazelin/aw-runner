# aw-runner

Long-running GitHub Actions runner with Cloudflare Tunnel + FastAPI + gh copilot CLI.

## Setup

See `docs/plans/2026-03-06-runner-tunnel-design.md` for full architecture.

### Required Secrets (GitHub Repo Settings)

| Secret | Purpose |
|--------|---------|
| `CF_TUNNEL_TOKEN` | cloudflared tunnel auth |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `RUNNER_API_KEY` | Shared secret between Worker and FastAPI |
| `GH_PAT` | Personal access token for self-trigger |

### Deploy Worker

```bash
cd worker
npm install
wrangler secret put RUNNER_URL        # e.g. https://runner.yourdomain.com
wrangler secret put RUNNER_API_KEY
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler deploy
```

### Register Telegram Webhook

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<worker>.workers.dev/<TELEGRAM_SECRET_PATH>"
```

### Start Runner

```bash
gh workflow run runner.yml
```
