#!/usr/bin/env python3
"""Reddit ニュース収集 + Claude Haiku 日本語要約（RSS XML & Markdown 出力）"""

import html
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import feedparser
import subprocess
import anthropic
from dotenv import load_dotenv

load_dotenv()

# ─── 設定 ─────────────────────────────────────────────────────────────────────
SUBREDDITS = [
    # ニュース・国際
    "worldnews", "news", "geopolitics", "technology",
    "science", "business", "economics", "environment",
    "europe", "asia",
    # マーケティング・広告
    "marketing", "digital_marketing", "advertising",
    "socialmedia", "entrepreneur",
]

POSTS_PER_SUBREDDIT = 3
RSS_FETCH_LIMIT = 10

SYSTEM_PROMPT = (
    "あなたは世界のニュースを日本語で端的に要約するアシスタントです。"
    "指定されたフォーマットで簡潔に回答してください。"
)

# ─── RSS 取得 ─────────────────────────────────────────────────────────────────
def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def fetch_rss(url: str) -> bytes:
    result = subprocess.run(
        [
            "curl", "-s", "-L", "--max-time", "15",
            "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "-H", "Accept-Language: en-US,en;q=0.5",
            url,
        ],
        capture_output=True,
        timeout=20,
    )
    return result.stdout


def fetch_posts(subreddit_name: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit_name}/hot.rss?limit={RSS_FETCH_LIMIT}"
    posts = []
    try:
        content = fetch_rss(url)
        if not content:
            raise ValueError("空のレスポンス")
        feed = feedparser.parse(content)
        for entry in feed.entries:
            posts.append({
                "title": entry.title,
                "url": entry.link,
                "subreddit": subreddit_name,
                "selftext": strip_html(entry.get("summary", ""))[:800],
            })
            if len(posts) >= POSTS_PER_SUBREDDIT:
                break
    except Exception as e:
        print(f"  ⚠️  r/{subreddit_name} 取得エラー: {e}", file=sys.stderr)
    return posts


# ─── Claude Haiku 要約 ────────────────────────────────────────────────────────
def summarize(client: anthropic.Anthropic, post: dict) -> tuple[str, str]:
    content = f"タイトル: {post['title']}"
    if post["selftext"]:
        content += f"\n\n本文抜粋:\n{post['selftext']}"

    prompt = (
        f"{content}\n\n"
        "以下のフォーマットで回答してください：\n\n"
        "【日本語タイトル】\n（タイトルを自然な日本語に翻訳）\n\n"
        "【要約】\n（3行以内で端的に）"
    )
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text
        jp_title, summary = post["title"], text.strip()
        if "【日本語タイトル】" in text and "【要約】" in text:
            parts = text.split("【要約】")
            jp_title = parts[0].replace("【日本語タイトル】", "").strip()
            summary = parts[1].strip()
        return jp_title, summary
    except Exception as e:
        print(f"  ⚠️  要約エラー: {e}", file=sys.stderr)
        return post["title"], "（要約の取得に失敗しました）"


# ─── 出力生成 ─────────────────────────────────────────────────────────────────
def build_rss_xml(results: list[dict], now: datetime) -> str:
    pub_date = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = ""
    for r in results:
        items += f"""
    <item>
      <title>{html.escape(r['jp_title'])}</title>
      <link>{html.escape(r['url'])}</link>
      <description>{html.escape(r['summary'])}</description>
      <category>{html.escape('r/' + r['subreddit'])}</category>
      <guid isPermaLink="true">{html.escape(r['url'])}</guid>
      <pubDate>{pub_date}</pubDate>
    </item>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Reddit ニュース日本語まとめ</title>
    <link>https://reddit.com</link>
    <description>世界のRedditホット記事を Claude Haiku で日本語要約</description>
    <lastBuildDate>{pub_date}</lastBuildDate>
    <language>ja</language>{items}
  </channel>
</rss>
"""


def build_markdown(results: list[dict], now: datetime) -> str:
    header = (
        f"# 🌍 Reddit ニュースまとめ {now.strftime('%Y-%m-%d')}\n\n"
        f"> 収集日時: {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"> 合計: {len(results)} 件\n\n"
    )
    items = []
    for r in results:
        items.append(
            "---\n"
            f"📌 {r['jp_title']}\n"
            f"🔗 {r['url']}\n"
            f"📝 要約：{r['summary']}\n"
            f"🌐 ソース：r/{r['subreddit']}\n"
            "---"
        )
    return header + "\n\n".join(items) + "\n"


# ─── メイン ───────────────────────────────────────────────────────────────────
def main() -> None:
    client = anthropic.Anthropic()

    print("🔍 Reddit ニュース収集を開始します...\n")

    all_posts: list[dict] = []
    seen_urls: set[str] = set()

    for subreddit in SUBREDDITS:
        print(f"  📡 r/{subreddit} を取得中...")
        posts = fetch_posts(subreddit)
        added = 0
        for p in posts:
            if p["url"] not in seen_urls:
                seen_urls.add(p["url"])
                all_posts.append(p)
                added += 1
        print(f"     → {added} 件追加（合計 {len(all_posts)} 件）")

    print(f"\n✅ {len(all_posts)} 件収集完了。AI 要約を生成中...\n")

    results: list[dict] = []
    for i, post in enumerate(all_posts, 1):
        print(f"  🤖 [{i:2d}/{len(all_posts)}] {post['title'][:60]}...")
        jp_title, summary = summarize(client, post)
        results.append({**post, "jp_title": jp_title, "summary": summary})

    now = datetime.utcnow()

    # docs/ に RSS XML を保存（GitHub Pages 用）
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    rss_file = docs_dir / "feed.xml"
    rss_file.write_text(build_rss_xml(results, now), encoding="utf-8")
    print(f"\n📡 RSS 保存完了: {rss_file}")

    # output/ に Markdown を保存
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    md_file = output_dir / f"news_{now.strftime('%Y-%m-%d')}.md"
    md_file.write_text(build_markdown(results, now), encoding="utf-8")
    print(f"💾 MD  保存完了: {md_file}")


if __name__ == "__main__":
    main()
