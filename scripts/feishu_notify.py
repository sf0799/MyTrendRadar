#!/usr/bin/env python3
"""Send TrendRadar notification to Feishu with AI analysis + hot topics."""
import json, os, re, glob, urllib.request, sys
from datetime import datetime


def extract_ai_analysis(html):
    """Extract AI analysis sections from TrendRadar HTML report."""
    sections = []
    # Find all ai-blocks: <div class="ai-block">...</div>
    blocks = re.findall(
        r'<div\s+class="ai-block"[^>]*>.*?<div\s+class="ai-block-title"[^>]*>(.*?)</div>\s*'
        r'<div\s+class="ai-block-content"[^>]*>(.*?)</div>\s*</div>',
        html, re.DOTALL
    )
    for title, content in blocks:
        title_text = re.sub(r'<[^>]+>', '', title).strip()
        content_text = re.sub(r'<[^>]+>', '', content).strip()
        content_text = re.sub(r'&nbsp;', ' ', content_text)
        content_text = re.sub(r'&lt;', '<', content_text)
        content_text = re.sub(r'&gt;', '>', content_text)
        content_text = re.sub(r'&amp;', '&', content_text)
        content_text = re.sub(r'\s*\n\s*', '\n', content_text)
        content_text = content_text.strip()
        if content_text:
            sections.append((title_text, content_text))
    return sections


def extract_news_titles(html):
    """Extract hot topic titles from TrendRadar HTML report."""
    items = []

    # Find news-item-title divs (keyword-display items)
    titles = re.findall(r'class="new-item-title"[^>]*>(.*?)</div>', html, re.DOTALL)
    for t in titles:
        text = re.sub(r'<[^>]+>', '', t).strip()
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        if text and len(text) > 3:
            items.append(text)

    # Try word-group titles too (keyword headers)
    word_headers = re.findall(r'class="word-name"[^>]*>(.*?)</div>', html, re.DOTALL)
    for h in word_headers:
        text = re.sub(r'<[^>]+>', '', h).strip()
        text = re.sub(r'&nbsp;', ' ', text)
        if text and len(text) > 1 and text not in items:
            items.append(f"【{text}】")

    return items


def build_feishu_card(ai_sections, news_items):
    """Build a Feishu interactive card message (more reliable than post)."""
    now = datetime.utcnow().strftime("%Y-%m-%d")
    elements = []

    # Title header
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**📡 热点日报**  |  {now}"}
    })

    # ── AI Analysis Section ──
    if ai_sections:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "**✨ AI 热点分析**"}
        })

        for title_text, content_text in ai_sections:
            lines = []
            for line in content_text.split('\n'):
                line = line.strip()
                if line:
                    if len(line) > 200:
                        line = line[:197] + "..."
                    lines.append(line)

            if lines:
                md_content = "\n".join(lines)
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": f"**▎{title_text}**\n{md_content}"}
                })

    # ── News Section ──
    if news_items:
        elements.append({"tag": "hr"})
        news_lines = []
        for item in news_items[:25]:
            display = item[:80] + "..." if len(item) > 80 else item
            news_lines.append(f"• {display}")

        if news_lines:
            md_content = "\n".join(news_lines)
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**📋 今日热点话题**\n{md_content}"}
            })

        if len(news_items) > 25:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"...还有 {len(news_items) - 25} 条"}
            })

    # Footer
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "🤖 TrendRadar 自动推送"}]
    })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📡 热点日报"},
            "template": "blue"
        },
        "elements": elements
    }

    return json.dumps(card, ensure_ascii=False)


def main():
    try:
        _do_main()
    except Exception as e:
        import traceback
        print(f"❌ Fatal: {e}")
        traceback.print_exc()
        # Try to send a fallback text message
        try:
            app_id = os.environ.get("FEISHU_APP_ID", "")
            app_secret = os.environ.get("FEISHU_APP_SECRET", "")
            chat_id = os.environ.get("FEISHU_CHAT_ID", "")
            run_url = os.environ.get("RUN_URL", "")
            if all([app_id, app_secret, chat_id]):
                _send_text(app_id, app_secret, chat_id,
                          f"📡 热点日报\n推送脚本错误: {e}\n查看详情: {run_url}")
        except:
            pass
        sys.exit(1)


def _do_main():
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    chat_id = os.environ.get("FEISHU_CHAT_ID", "")
    run_url = os.environ.get("RUN_URL", "")

    if not all([app_id, app_secret, chat_id]):
        print("⚠️ Missing Feishu credentials, skipping")
        return

    # Find latest HTML report
    html_content = None
    print(f"🔍 CWD: {os.getcwd()}")
    html_dir = "output/html"
    if os.path.isdir(html_dir):
        print(f"  html dirs: {[d for d in os.listdir(html_dir) if os.path.isdir(os.path.join(html_dir, d))]}")
    else:
        print(f"  '{html_dir}' dir not found")
    
    for pattern in ["output/html/latest/current.html", "output/html/latest/daily.html",
                     "output/html/latest/*.html",
                     "output/html/*/current.html", "output/html/*/daily.html",
                     "output/html/*/*.html"]:
        paths = sorted(glob.glob(pattern), reverse=True)
        if not paths:
            paths = sorted(glob.glob(pattern.replace("2026-06-16", "2026-*")), reverse=True)
        for path in paths:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    html_content = f.read()
                if html_content and len(html_content) > 1000:
                    print(f"📄 Found report: {path} ({len(html_content)} bytes)")
                    break
        if html_content:
            break

    if not html_content:
        print("⚠️ No HTML report found")
        text = f"📡 热点日报\n暂无内容\n查看详情: {run_url}"
        _send_text(app_id, app_secret, chat_id, text)
        return

    # Extract AI analysis and news items
    ai_sections = extract_ai_analysis(html_content)
    news_items = extract_news_titles(html_content)

    print(f"📊 AI sections: {len(ai_sections)}, news items: {len(news_items)}")

    if not ai_sections and not news_items:
        text = f"📡 热点日报\n暂无匹配热点\n查看详情: {run_url}"
        _send_text(app_id, app_secret, chat_id, text)
        return

    # Build and send rich card message
    card_data = build_feishu_card(ai_sections, news_items)
    _send_card(app_id, app_secret, chat_id, card_data)


def _get_token(app_id, app_secret):
    """Get Feishu tenant access token."""
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=15)
    token = json.loads(resp.read()).get("tenant_access_token", "")
    if not token:
        print("❌ Failed to get Feishu token")
    return token


def _send_text(app_id, app_secret, chat_id, text):
    """Send a plain text message."""
    token = _get_token(app_id, app_secret)
    if not token:
        return

    content = json.dumps({"text": text})
    msg = json.dumps({"receive_id": chat_id, "msg_type": "text", "content": content})

    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=msg.encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=15)
    result = json.loads(resp.read())
    if result.get("code") == 0:
        print(f"✅ Text sent: {result['data']['message_id']}")
    else:
        print(f"❌ Error: {result}")


def _send_card(app_id, app_secret, chat_id, card_content_str):
    """Send an interactive card message."""
    token = _get_token(app_id, app_secret)
    if not token:
        return

    card_content = json.loads(card_content_str)
    content = json.dumps(card_content, ensure_ascii=False)
    msg = json.dumps({
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": content
    }, ensure_ascii=False)

    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=msg.encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        if result.get("code") == 0:
            print(f"✅ Post sent: {result['data']['message_id']}")
        else:
            print(f"❌ API Error: {result.get('msg', result)}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"❌ HTTP {e.code}: {body}")
        print(f"   Content length: {len(msg)} chars")
        raise


if __name__ == "__main__":
    main()
