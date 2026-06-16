#!/usr/bin/env python3
"""Send TrendRadar notification to Feishu group chat with news content."""
import json, os, re, glob, urllib.request

def extract_news(path):
    """Try to extract news items from a file."""
    if not os.path.exists(path):
        print(f"  Not found: {path}")
        return None
    
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    
    print(f"  Read {path} ({len(content)} bytes)")
    
    items = []
    
    # Try HTML li items
    matches = re.findall(r'<li[^>]*>(.*?)</li>', content, re.DOTALL)
    for m in matches:
        text = re.sub(r'<[^>]+>', '', m).strip()
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        if text and len(text) > 5:
            items.append(text)
    
    if items:
        print(f"  Found {len(items)} list items")
        return items
    
    # Try to find any text content in the HTML
    text = re.sub(r'<[^>]+>', '\n', content)
    text = re.sub(r'&nbsp;', ' ', text)
    lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 5]
    lines = [l for l in lines if not l.startswith('{') and not l.startswith('<')]
    print(f"  Found {len(lines)} text lines")
    return lines[:20] if lines else None


def main():
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    chat_id = os.environ.get("FEISHU_CHAT_ID", "")
    run_url = os.environ.get("RUN_URL", "")

    if not all([app_id, app_secret, chat_id]):
        print("Missing Feishu credentials, skipping")
        return

    # Debug: list output files
    print("Checking output files:")
    for f in glob.glob("output/**/*", recursive=True):
        if os.path.isfile(f):
            print(f"  {f} ({os.path.getsize(f)} bytes)")

    # Try to get news from various possible file locations
    news_items = None
    for path in sorted(glob.glob("output/html/latest/*.html")):
        news_items = extract_news(path)
        if news_items:
            break
    
    if not news_items:
        for path in sorted(glob.glob("output/html/**/*.html"), reverse=True):
            news_items = extract_news(path)
            if news_items:
                break
    
    if not news_items:
        # Try text files
        for path in sorted(glob.glob("output/**/*.txt"), reverse=True):
            news_items = extract_news(path)
            if news_items:
                break

    # Build message text
    if news_items:
        summary = "\n".join(f"• {item[:60]}{'...' if len(item) > 60 else ''}" for item in news_items[:15])
        text = f"📡 TrendRadar 热点日报\n\n{summary}\n\n📊 共 {len(news_items)} 条热点\n查看详情: {run_url}"
    else:
        text = f"📡 TrendRadar 热点日报\n暂无匹配热点\n查看详情: {run_url}"

    print(f"\nMessage length: {len(text)} chars")
    print(f"Preview: {text[:200]}")

    # Get Feishu access token
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=15)
    token = json.loads(resp.read()).get("tenant_access_token", "")
    if not token:
        print("Failed to get Feishu token")
        return

    # Send message
    content = json.dumps({"text": text})
    msg = json.dumps({
        "receive_id": chat_id,
        "msg_type": "text",
        "content": content
    })

    req2 = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=msg.encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    resp2 = urllib.request.urlopen(req2, timeout=15)
    result = json.loads(resp2.read())
    if result.get("code") == 0:
        print(f"✅ Feishu notification sent: {result['data']['message_id']}")
    else:
        print(f"❌ Feishu API error: {result}")

if __name__ == "__main__":
    main()
