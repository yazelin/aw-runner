# Setup Guide

## 架構概覽

```
Telegram 用戶
     ↓ 傳訊息
Telegram Bot
     ↓ webhook
Cloudflare Worker          ← 公開接收 webhook，轉發請求
     ↓ 讀 KV runner_url
GitHub Actions Runner      ← 長期運行 (6h 接力)
     ↓ cloudflared quick tunnel 暴露
FastAPI Server (port 8000)
     ↓ gh copilot suggest
回覆 Telegram
```

## 前置需求

安裝以下工具：

| 工具 | 安裝方式 |
|------|---------|
| [gh CLI](https://cli.github.com) | `brew install gh` / apt / winget |
| [Node.js](https://nodejs.org) 18+ | 官網下載或 nvm |
| Python 3.10+ | 系統內建或官網 |
| curl, openssl | 系統內建 |

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

### 步驟 1：建立 GitHub Repo

```bash
gh repo create aw-runner --public --source=. --remote=origin --push
```

> Public repo 可使用無限 GitHub Actions 分鐘數。

### 步驟 2：建立 Cloudflare KV Namespace

```bash
cd worker
npm install
npx wrangler login          # 登入 Cloudflare
npx wrangler kv namespace create "RUNNER_KV"
```

記下輸出的 `id`，填入 `worker/wrangler.toml`：

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

#### GitHub PAT
1. 前往 https://github.com/settings/tokens
2. Generate new token (classic)
3. 勾選 **workflow** scope
4. 建立並複製 token

#### Runner API Key
自行生成隨機密鑰：

```bash
openssl rand -hex 32
```

### 步驟 4：設定 GitHub Secrets

```bash
gh secret set TELEGRAM_BOT_TOKEN --body "<token>"
gh secret set TELEGRAM_CHAT_ID   --body "<chat_id>"
gh secret set CF_ACCOUNT_ID      --body "<cloudflare_account_id>"
gh secret set CF_API_TOKEN       --body "<cloudflare_api_token>"
gh secret set KV_NAMESPACE_ID    --body "<kv_namespace_id>"
gh secret set RUNNER_API_KEY     --body "<random_key>"
gh secret set GH_PAT             --body "<github_pat>"
```

### 步驟 5：Deploy Cloudflare Worker

```bash
cd worker
echo "<RUNNER_API_KEY>"     | npx wrangler secret put RUNNER_API_KEY
echo "<TELEGRAM_BOT_TOKEN>" | npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler deploy
```

記下部署完成後的 Worker URL，例如：
`https://aw-runner-worker.xxx.workers.dev`

### 步驟 6：設定 Telegram Webhook

```bash
SECRET_PATH=$(openssl rand -hex 16)
WORKER_URL="https://aw-runner-worker.xxx.workers.dev"
BOT_TOKEN="你的 TELEGRAM_BOT_TOKEN"

curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WORKER_URL}/${SECRET_PATH}"
```

預期回應：`{"ok":true,"result":true,"description":"Webhook was set"}`

### 步驟 7：啟動 Runner

```bash
gh workflow run runner.yml
```

---

## 驗證

```bash
# 確認 runner 正在執行
gh run list --workflow=runner.yml --limit 1
# 預期 status: in_progress

# 傳訊息給你的 Telegram bot
# 預期在 10~30 秒內收到 gh copilot 的回覆
```

---

## Required GitHub Secrets 一覽

| Secret | 說明 |
|--------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token（來自 @BotFather） |
| `TELEGRAM_CHAT_ID` | 你的 Telegram chat ID |
| `CF_ACCOUNT_ID` | Cloudflare 帳號 ID |
| `CF_API_TOKEN` | Cloudflare API token（Workers KV 寫入權限） |
| `KV_NAMESPACE_ID` | Cloudflare KV namespace ID |
| `RUNNER_API_KEY` | Worker 與 FastAPI 之間的共享密鑰 |
| `GH_PAT` | GitHub PAT（workflow scope，用於 self-trigger） |

---

## 運作原理

1. **GitHub Actions** 啟動 `runner.yml` job（最長 6 小時）
2. FastAPI 在 port 8000 啟動
3. `cloudflared tunnel --url` 建立 quick tunnel，取得 `*.trycloudflare.com` URL
4. Runner 將 URL 寫入 Cloudflare KV（key: `runner_url`）
5. Telegram 訊息 → Worker 從 KV 讀取 URL → 轉發給 FastAPI
6. FastAPI 呼叫 `gh copilot suggest` → 回傳結果給 Telegram
7. job 結束前（5h55m 後）自動觸發下一個 run，實現無限接力

---

## 常見問題

**Q: Runner 沒有回應？**
- 確認 Actions tab 的 job 狀態是 `in_progress`
- 查看 job log 確認 tunnel URL 成功寫入 KV
- 確認 Telegram webhook 設定正確

**Q: `gh copilot` 沒有輸出？**
- 確認 `GH_PAT` 有效且帳號有 GitHub Copilot 訂閱
- 查看 job log 的 `_process` 錯誤訊息

**Q: 每 6 小時有空窗期嗎？**
- 極少數情況下 self-trigger 和新 job 啟動之間可能有 1~2 分鐘空窗
- 可設定 cron `'0 */6 * * *'` 作為備援（已內建）
