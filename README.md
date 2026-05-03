# 🛰️ LLM Trend Radar

每週一自動掃描 GitHub 上 LLM / AI Agent 領域最熱門的 Top 10 專案，用 OpenAI API 產生中文技術摘要，推送到 Discord。

## 📦 功能

- 🔍 篩選最近一個月內活躍、星星數最高的 LLM / AI Agent 專案
- 🤖 用 OpenAI 自動產生三層分析：**技術核心 / 商業應用 / 技術實作細節**
- 📨 結果推送到 Discord（也會 commit 一份 Markdown 報告到 `reports/`）
- ⏰ 每週一 台灣時間 09:00 自動執行（GitHub Actions cron）

## 🚀 設定步驟

### 1. Fork / Clone 這個 repo 到自己的 GitHub

### 2. 設定 Secrets

到 repo 的 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`，新增：

| Secret 名稱 | 取得方式 |
|---|---|
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `DISCORD_WEBHOOK_URL` | Discord 頻道設定 → 整合 → Webhook → 新增 → 複製 URL |

> `GITHUB_TOKEN` 不需要手動設，Actions 會自動注入。

### 3. （可選）調整參數

編輯 `.github/workflows/weekly.yml` 的 `env` 區塊：

```yaml
OPENAI_MODEL: gpt-4o-mini   # 可換成 gpt-4o, o3-mini 等
TOP_N: "10"                  # 想分析的專案數量
```

執行時間調整 `cron` 欄位（注意 GitHub Actions 用 UTC 時間）：
- 每週一台灣時間 09:00 → `"0 1 * * 1"`
- 每週五台灣時間 18:00 → `"0 10 * * 5"`

### 4. 手動測試

到 `Actions` 分頁 → 選 `Weekly LLM Trend Radar` → `Run workflow`，立刻測試一次。

## 🧪 本地測試

```bash
pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export GITHUB_TOKEN="ghp_..."   # 可選，沒有的話 GitHub API 會用 unauthenticated rate limit

python src/main.py
```

## 📁 專案結構

```
llm-trend-radar/
├── .github/workflows/weekly.yml   # 每週排程
├── src/main.py                    # 主程式
├── prompts/summarize.md           # OpenAI 摘要 prompt 範本
├── reports/                       # 自動產生的歷史報告
├── requirements.txt
└── README.md
```

## 💰 成本估算

以 `gpt-4o-mini` + Top 10 估算：
- 每次執行約消耗 30k~50k tokens（README + 摘要）
- 每週成本約 **$0.01 ~ $0.03 USD**
- 一年大約 **$1 USD 左右**

換成 `gpt-4o` 大約貴 15~20 倍，仍在合理範圍。

## 🔧 客製化方向

- **改通知管道**：把 `send_to_discord()` 換成 Slack / Telegram / Email
- **改篩選範圍**：調整 `main.py` 的 `pushed:>=` 和 `SEARCH_KEYWORDS`
- **改 prompt 風格**：直接編輯 `prompts/summarize.md`
- **加上去重**：用 `reports/` 目錄記錄歷史，跳過上週已分析過的 repo
