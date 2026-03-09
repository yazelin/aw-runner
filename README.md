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
     ├─ 讀 KV 取得 runner_a_url / runner_b_url
     ├─ Health check 兩個 runner（A 優先）
     ↓ POST /task → 活著的 runner
FastAPI Server（GitHub Actions Runner A 或 B）
     ↓ copilot --autopilot --yolo -p
Copilot CLI（AI Agent）
     ↓ 呼叫 .github/scripts/send_telegram_message.py
回覆 Telegram
```

## 高可用（HA）雙 Runner 架構

```
Runner A [PRIMARY]:   |======== 5.5h ========|              |======== 5.5h ========|
Runner B [SECONDARY]:          |======== 5.5h ========|              |======== 5.5h ========|
                               ↑                      ↑
                          A 觸發 B (~2.5h)        B 觸發 A (~2.5h)

服務覆蓋:              |--A--|--A+B--|--B--|--A+B--|--A--|--A+B--|--B--|
                              ↑ 永遠至少一個在線 ↑
```

- **Runner-A（PRIMARY）**：主要服務節點，Worker 優先路由到 A
- **Runner-B（SECONDARY）**：備援節點，A 不可用時自動接管
- 每個 runner 跑 ~5.5 小時，在 GitHub Actions 6h 限制前優雅結束
- 啟動 ~2.5 小時後檢查對方，若對方不在就觸發，自然形成 ~3h 錯開
- **零停機**：一個在重啟時，另一個一定在服務中
- 不需要獨立 watchdog — 互相監控、互相觸發

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
| `GH_PAT` | GitHub PAT（`workflow` scope，用於互相觸發） |
| `COPILOT_GITHUB_TOKEN` | Fine-grained PAT（Copilot Requests 權限） |

## 專案結構

```
aw-runner/
├── .github/
│   ├── mcp-config.json          # Copilot MCP 設定
│   ├── scripts/
│   │   └── send_telegram_message.py  # Copilot 呼叫此腳本回覆
│   └── workflows/
│       ├── runner-a.yml         # PRIMARY runner（5.5h 循環）
│       └── runner-b.yml         # SECONDARY runner（5.5h 循環）
├── server/
│   ├── main.py                  # FastAPI server
│   └── requirements.txt
├── worker/
│   ├── src/index.ts             # Cloudflare Worker（雙 runner failover）
│   └── wrangler.toml
├── docs/
│   ├── index.html               # GitHub Pages 狀態頁（雙 runner 監控）
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

透過 Worker 查詢狀態（含雙 runner 資訊）：

```bash
curl https://aw-runner-worker.yazelinj303.workers.dev/status
# 回傳：
# {
#   "status": "ok",
#   "active_slot": "a",
#   "runner_a": { "status": "ok", "url": "https://..." },
#   "runner_b": { "status": "ok", "url": "https://..." }
# }
```

## 安全

- **Worker**：驗證 `chat_id` 白名單，未授權請求靜默忽略
- **FastAPI**：驗證 `x-api-key`，無效 key 回 401
- **Tunnel URL**：`trycloudflare.com` 隨機子網域，每次重啟都不同
- **雙 runner 隔離**：各自獨立的 tunnel，互不影響
