"""
LLM Trend Radar
每週自動抓取 GitHub 上 LLM / AI Agent 領域最熱門的 Top 10 專案，
用 OpenAI API 產生中文摘要（技術核心 / 商業應用 / 技術實作細節），
並推送到 Discord。
"""

import os
import sys
import json
import time
import datetime as dt
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ---------- 設定 ----------
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
TOP_N = int(os.environ.get("TOP_N", "10"))

# LLM / AI Agent 相關關鍵字（GitHub topic + 關鍵字 OR）
SEARCH_KEYWORDS = [
    "llm",
    "agent",
    "ai-agent",
    "rag",
    "llm-agent",
    "multi-agent",
    "autonomous-agent",
]

PROMPT_PATH = Path(__file__).parent / "summarize.md"
OUTPUT_DIR = Path(__file__).parent / "reports"


# ---------- GitHub ----------
def search_trending_repos(top_n: int = 10) -> list[dict[str, Any]]:
    """搜尋最近一個月內、與 LLM/AI Agent 相關、星星增加最多的專案。

    GitHub Search API 的策略：用 `pushed:>=YYYY-MM-DD` + `topic:` 關鍵字組合，
    再以 stars 降序排序，取前 N 名。
    """
    one_month_ago = (dt.date.today() - dt.timedelta(days=30)).isoformat()

    # 用 topic OR 組合避免單一關鍵字遺漏
    topic_query = " ".join(f"topic:{kw}" for kw in SEARCH_KEYWORDS[:3])
    # GitHub 不支援 topic OR，改用 in:topics + 關鍵字
    keyword_query = " OR ".join(SEARCH_KEYWORDS)

    query = f"({keyword_query}) in:name,description,topics pushed:>={one_month_ago}"

    url = "https://api.github.com/search/repositories"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": top_n,
    }

    print(f"[GitHub] Query: {query}")
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    print(f"[GitHub] 取得 {len(items)} 個專案")
    return items


def fetch_readme(full_name: str) -> str:
    """抓 repo 的 README，最多取前 8000 字（避免 token 爆掉）。"""
    url = f"https://api.github.com/repos/{full_name}/readme"
    headers = {"Accept": "application/vnd.github.raw"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.text[:8000]
    except Exception as e:
        print(f"[README] {full_name} 讀取失敗: {e}")
    return ""


# ---------- OpenAI 摘要 ----------
def load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def summarize_repo(client: OpenAI, repo: dict, readme: str) -> str:
    """用 OpenAI 產生中文摘要。"""
    template = load_prompt_template()
    user_content = template.format(
        name=repo["full_name"],
        description=repo.get("description") or "(無描述)",
        stars=repo["stargazers_count"],
        language=repo.get("language") or "未知",
        url=repo["html_url"],
        topics=", ".join(repo.get("topics", [])) or "(無)",
        readme=readme or "(README 無法取得)",
    )

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是同時具備技術深度與商業敏感度的 AI 產品顧問。"
                    "你的分析必須讓工程師能立即複製實作，也讓產品經理能直接判斷商業可行性。"
                    "禁止使用「強大」「先進」「創新」等空泛形容詞，只說具體技術事實。"
                    "回覆使用繁體中文。"
                ),
            },
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


# ---------- Discord ----------
def send_to_discord(content: str) -> None:
    """Discord webhook 訊息上限 2000 字，超過要分段。"""
    chunks = []
    current = ""
    for line in content.split("\n"):
        if len(current) + len(line) + 1 > 1900:
            chunks.append(current)
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current)

    for i, chunk in enumerate(chunks):
        payload = {"content": chunk}
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
        if resp.status_code >= 300:
            print(f"[Discord] 第 {i+1} 段發送失敗: {resp.status_code} {resp.text}")
        else:
            print(f"[Discord] 第 {i+1}/{len(chunks)} 段已發送")
        time.sleep(1)  # 避免 rate limit


# ---------- 主流程 ----------
def main() -> int:
    today = dt.date.today().isoformat()
    print(f"=== LLM Trend Radar | {today} ===")

    repos = search_trending_repos(TOP_N)
    if not repos:
        print("沒有找到任何符合條件的專案")
        return 1

    client = OpenAI(api_key=OPENAI_API_KEY)

    # 標題訊息
    header = f"# 🛰️ LLM Trend Radar — {today}\n本週 LLM / AI Agent 領域 Top {len(repos)} 趨勢專案：\n"
    send_to_discord(header)

    # 累積 markdown 報告
    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
    report_path = OUTPUT_DIR / f"{today}.md"
    report_lines = [f"# LLM Trend Radar — {today}\n"]

    for idx, repo in enumerate(repos, start=1):
        full_name = repo["full_name"]
        print(f"\n[{idx}/{len(repos)}] 處理 {full_name}")

        readme = fetch_readme(full_name)
        try:
            summary = summarize_repo(client, repo, readme)
        except Exception as e:
            print(f"[OpenAI] 摘要失敗: {e}")
            summary = f"摘要失敗: {e}"

        block = (
            f"## {idx}. [{full_name}]({repo['html_url']}) ⭐ {repo['stargazers_count']:,}\n"
            f"> {repo.get('description') or ''}\n\n"
            f"{summary}\n"
        )
        report_lines.append(block)
        send_to_discord(block)

    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\n報告已存至 {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
