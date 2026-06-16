#!/usr/bin/env python3
"""Send TrendRadar notification to Feishu group chat with news content."""
import json, os, re, urllib.request
from html.parser import HTMLParser

def extract_news_from_html(html_path):
    """Extract news items from TrendRadar HTML report."""
    if not os.path.exists(html_path):
        return None
    
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    items = []
    # Find all list items in the report
    matches = re.findall(r'<li[^>]*>.*?</li>', html, re.DOTALL)
    for m in matches:
        text = re.sub(r'<[^>]+>', '', m).strip()
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        if text and len(text) > 3:
            items.append(text)
    
    return items


def main():
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    chat_id = os.environ.get("FEISHU_CHAT_ID", "")
    run_url = os.environ.get("RUN_URL", "")

    if not all([app_id, app_secret, chat_id]):
        print("Missing Feishu credentials, skipping")
        return

    # Try to get news from HTML report
    news_items = []
    for path in ["output/html/latest/current.html", "output/html/latest/trending.html"]:
        items = extract_news_from_html(path)
        if items:
            news_items = items
            break

    # Build message text
    if news_items:
        summary = "\n".join(f"• {item[:60]}{'...' if len(item) > 60 else ''}" for item in news_items[:15])
        text = f"📡 TrendRadar 热点日报\n\n{summary}\n\n📊 共 {len(news_items)} 条热点\n查看详情: {run_url}"
    else:
        text = f"📡 TrendRadar 热点日报\n暂无匹配热点\n查看详情: {run_url}"

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
