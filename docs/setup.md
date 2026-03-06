# Setup Guide

## 架構概覽

```
Telegram 用戶
     ↓ 傳訊息
Telegram Bot
     ↓ webhook（隨機 secret path 保護）
Cloudflare Worker
     ├─ 驗證 chat_id 白名單
     ├─ 讀 KV runner_url
     ↓ POST /task (x-api-key 保護)
FastAPI Server（GitHub Actions Runner）
     ↓ copilot --autopilot --yolo -p
Copilot CLI（AI Agent，可呼叫 shell 工具）
     ↓ python3 .github/scripts/send_telegram_message.py
回覆 Telegram
```

Runner 每 6 小時接力一次（self-trigger），啟動後主動發 Telegram 上線通知。

---

## 前置需求

| 工具 | 安裝方式 |
|------|---------|
| [gh CLI](https://cli.github.com) | `brew install gh` / apt / winget |
| [Node.js](https://nodejs.org) 18+ | 官網下載或 nvm |
| Python 3.10+ | 系統內建或官網 |
| curl, openssl | 系統內建 |

---

## 快速安裝（建議）

**Fork 或 clone 本 repo，然後執行：**

```bash
git clone https://github.com/yazelin/aw-runner.git
cd aw-runner
cd worker && npm install && cd ..
bash scripts/setup.sh
```

腳本會一步一步引導你完成所有設定，約 10 分鐘。

---

## 手動安裝（逐步說明）

### 步驟 1：建立 GitHub Repo（Public）

```bash
gh repo create aw-runner --public --source=. --remote=origin --push
```

> **Public repo** 可使用無限 GitHub Actions 分鐘數。Private repo 免費方案每月只有 2,000 分鐘。

### 步驟 2：建立 Cloudflare KV Namespace

```bash
cd worker
npm install
npx wrangler login          # 登入 Cloudflare
npx wrangler kv namespace create "RUNNER_KV"
```

記下輸出的 `id`，確認已填入 `worker/wrangler.toml`：

```toml
[[kv_namespaces]]
binding = "RUNNER_KV"
id = "你的-namespace-id"
```

### 步驟 3：取得各項 Token

#### Telegram Bot Token
1. 在 Telegram 找 **@BotFather**
2. 傳送 `/newbot`，依指示建立 bot
3. 收到 token，格式：`123456789:AAF...`

#### Telegram Chat ID
1. 在 Telegram 找 **@userinfobot**
2. 傳任意訊息
3. 收到你的 Chat ID（純數字）

#### Cloudflare API Token
1. 前往 https://dash.cloudflare.com/profile/api-tokens
2. Create Token → 選範本 **Edit Cloudflare Workers**
3. 確認 Account Resources 選到你的帳號
4. 建立並複製 token

#### Cloudflare Account ID
登入 Cloudflare Dashboard，右側邊欄可找到 Account ID。

#### GitHub PAT（workflow scope）
1. 前往 https://github.com/settings/tokens
2. Generate new token (classic)
3. 勾選 **workflow** scope
4. 建立並複製 token

#### Copilot GitHub Token（Fine-grained）
1. 前往 https://github.com/settings/tokens → Fine-grained tokens
2. Generate new token
3. Permissions → **Copilot API → Read-only**
4. 建立並複製 token

> 此 token 需要帳號有 **GitHub Copilot 訂閱**。

#### Runner API Key
```bash
openssl rand -hex 32
```

### 步驟 4：設定 GitHub Secrets

```bash
gh secret set TELEGRAM_BOT_TOKEN    --body "<token>"
gh secret set TELEGRAM_CHAT_ID      --body "<chat_id>"
gh secret set CF_ACCOUNT_ID         --body "<cloudflare_account_id>"
gh secret set CF_API_TOKEN          --body "<cloudflare_api_token>"
gh secret set KV_NAMESPACE_ID       --body "<kv_namespace_id>"
gh secret set RUNNER_API_KEY        --body "<random_key>"
gh secret set GH_PAT                --body "<github_pat>"
gh secret set COPILOT_GITHUB_TOKEN  --body "<copilot_pat>"
```

### 步驟 5：Deploy Cloudflare Worker

```bash
cd worker
echo "<RUNNER_API_KEY>"     | npx wrangler secret put RUNNER_API_KEY
echo "<TELEGRAM_BOT_TOKEN>" | npx wrangler secret put TELEGRAM_BOT_TOKEN
echo "<TELEGRAM_CHAT_ID>"   | npx wrangler secret put ALLOWED_CHAT_ID
npx wrangler deploy
```

記下部署後的 Worker URL：`https://aw-runner-worker.<subdomain>.workers.dev`

### 步驟 6：設定 Telegram Webhook

```bash
SECRET_PATH=$(openssl rand -hex 16)
WORKER_URL="https://aw-runner-worker.<subdomain>.workers.dev"
BOT_TOKEN="你的 TELEGRAM_BOT_TOKEN"

curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WORKER_URL}/${SECRET_PATH}"
```

預期回應：`{"ok":true,"result":true,"description":"Webhook was set"}`

### 步驟 7：啟動 Runner

```bash
gh workflow run runner.yml
```

Runner 啟動後（約 2~3 分鐘）會主動傳 Telegram 通知：
```
🟢 aw-runner 已上線
Tunnel: https://xxxx.trycloudflare.com
Run: https://github.com/...
```

---

## 驗證

```bash
# 查 runner 狀態
curl https://aw-runner-worker.<subdomain>.workers.dev/status

# 確認 workflow 執行中
gh run list --workflow=runner.yml --limit 1
# 預期 status: in_progress
```

狀態頁：`https://<username>.github.io/aw-runner/`

傳訊息給 bot 測試，約 10~60 秒後收到 Copilot AI 回覆。

---

## Required Secrets 一覽

| Secret | 說明 |
|--------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token（@BotFather） |
| `TELEGRAM_CHAT_ID` | 允許使用 bot 的 chat ID（白名單） |
| `CF_ACCOUNT_ID` | Cloudflare 帳號 ID |
| `CF_API_TOKEN` | Cloudflare API token（Workers + KV 寫入） |
| `KV_NAMESPACE_ID` | Cloudflare KV namespace ID |
| `RUNNER_API_KEY` | Worker 與 FastAPI 共享密鑰 |
| `GH_PAT` | GitHub PAT（`workflow` scope，self-trigger 用） |
| `COPILOT_GITHUB_TOKEN` | Fine-grained PAT（Copilot Requests 權限） |

---

## 運作原理

1. **GitHub Actions** 啟動 `runner.yml` job（最長 6 小時）
2. 安裝 Copilot CLI (`npm install -g @github/copilot`) 及 Python 依賴
3. FastAPI 在 port 8000 啟動
4. `cloudflared tunnel --url` 建立 quick tunnel，取得 `*.trycloudflare.com` URL
5. Runner 將 URL 寫入 Cloudflare KV（`runner_url`）
6. 發送 Telegram 上線通知
7. Telegram 訊息 → Worker 驗證 → FastAPI `/task` → Copilot Agent 處理 → 回覆
8. 5h55m 後自動觸發下一個 run（6 小時接力）

---

## 安全層級

| 層 | 防護 |
|----|------|
| Webhook URL | 隨機 secret path，外人無法猜到 |
| Worker | 驗證 `chat_id`，非白名單靜默忽略 |
| FastAPI `/task` | 驗證 `x-api-key`，無效 key 回 401 |
| Tunnel URL | 隨機子網域，每次重啟都不同 |

---

## 常見問題

**Q: Runner 沒有回應？**
- 確認 Actions tab 的 job 狀態是 `in_progress`
- 打 `/status` endpoint 確認 runner 在線
- 確認你的 chat_id 在白名單內

**Q: Copilot 沒有回覆？**
- 確認 `COPILOT_GITHUB_TOKEN` 有效且帳號有 GitHub Copilot 訂閱
- 查看 Actions job log 確認 Copilot CLI 正常啟動

**Q: 每 6 小時有空窗期嗎？**
- 極少數情況下新 job 啟動前可能有 1~2 分鐘空窗
- 已內建 cron `'0 */6 * * *'` 作為備援觸發

**Q: 如何自訂 Copilot 的行為？**
- 編輯 `prompt.md` 修改系統提示詞
- 編輯 `.github/mcp-config.json` 加入 MCP servers（nanobanana、tavily 等）
