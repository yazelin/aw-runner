# aw-runner

長期運行的 GitHub Actions Runner，透過 Cloudflare Tunnel 暴露 FastAPI，以 GitHub Copilot CLI (`@github/copilot`) 作為 AI Agent，接收 Telegram 訊息並自動回覆。

**狀態頁：** https://yazelin.github.io/aw-runner/

## 架構

```
Telegram 用戶
     ↓ 傳訊息
Telegram Bot (@aw_runner_bot)
     ↓ webhook（隨機 secret path）
Cloudflare Worker
     ├─ 驗證 chat_id 白名單
     ├─ 讀 KV 取得 runner_url
     ↓ POST /task
FastAPI Server（GitHub Actions Runner）
     ↓ copilot --autopilot --yolo -p
Copilot CLI（AI Agent）
     ↓ 呼叫 .github/scripts/send_telegram_message.py
回覆 Telegram
```

Runner 每 6 小時自我觸發一次新 run 無限接力，啟動時主動發 Telegram 上線通知。

## 快速安裝

```bash
git clone https://github.com/yazelin/aw-runner.git
cd aw-runner
cd worker && npm install && cd ..
bash scripts/setup.sh
```

詳細說明見 [docs/setup.md](docs/setup.md)。

## 所需 Secrets

| Secret | 說明 |
|--------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token（來自 @BotFather） |
| `TELEGRAM_CHAT_ID` | 允許使用 bot 的 chat ID |
| `CF_ACCOUNT_ID` | Cloudflare 帳號 ID |
| `CF_API_TOKEN` | Cloudflare API token（Workers + KV 寫入） |
| `KV_NAMESPACE_ID` | Cloudflare KV namespace ID |
| `RUNNER_API_KEY` | Worker 與 FastAPI 之間的共享密鑰 |
| `GH_PAT` | GitHub PAT（`workflow` scope，用於 self-trigger） |
| `COPILOT_GITHUB_TOKEN` | Fine-grained PAT（Copilot Requests 權限） |

## 專案結構

```
aw-runner/
├── .github/
│   ├── mcp-config.json          # Copilot MCP 設定
│   ├── scripts/
│   │   └── send_telegram_message.py  # Copilot 呼叫此腳本回覆
│   └── workflows/
│       └── runner.yml           # 長跑 workflow（6h 接力）
├── server/
│   ├── main.py                  # FastAPI server
│   └── requirements.txt
├── worker/
│   ├── src/index.ts             # Cloudflare Worker
│   └── wrangler.toml
├── docs/
│   ├── index.html               # GitHub Pages 狀態頁
│   └── setup.md                 # 完整安裝說明
├── scripts/
│   └── setup.sh                 # 互動式安裝腳本
└── prompt.md                    # Copilot 系統提示詞
```

## API Endpoints

| Endpoint | 說明 |
|----------|------|
| `GET /health` | FastAPI 健康檢查 |
| `GET /status` | Runner uptime、tunnel URL |
| `POST /task` | 接收訊息並交給 Copilot 處理（需 `x-api-key`） |

透過 Worker 查詢狀態（含 CORS）：

```bash
curl https://aw-runner-worker.yazelinj303.workers.dev/status
```

## 安全

- **Worker**：驗證 `chat_id` 白名單，未授權請求靜默忽略
- **FastAPI**：驗證 `x-api-key`，無效 key 回 401
- **Tunnel URL**：`trycloudflare.com` 隨機子網域，每次重啟都不同
