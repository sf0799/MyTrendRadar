#!/usr/bin/env python3
"""Send TrendRadar notification to Feishu group chat with news content."""
import json, os, re, glob, urllib.request

def extract_news(path):
    if not os.path.exists(path):
        return None
    
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    
    items = []
    
    # Find news-item-title divs (TrendRadar HTML format)
    titles = re.findall(r'class="new-item-title"[^>]*>(.*?)</div>', content, re.DOTALL)
    for t in titles:
        text = re.sub(r'<[^>]+>', '', t).strip()
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        if text and len(text) > 3:
            items.append(text)
    
    # Try RSS items too
    rss_titles = re.findall(r'class="rss-item"[^>]*>.*?<div[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</div>', content, re.DOTALL)
    for t in rss_titles:
        text = re.sub(r'<[^>]+>', '', t).strip()
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        if text and len(text) > 3:
            items.append(f"[RSS] {text}")
    
    # Also try standalone items
    standalone_titles = re.findall(r'class="news-item"[^>]*>.*?<div[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</div>', content, re.DOTALL)
    for t in standalone_titles:
        text = re.sub(r'<[^>]+>', '', t).strip()
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        if text and len(text) > 3 and text not in items:
            items.append(text)
    
    return items if items else None


def main():
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    chat_id = os.environ.get("FEISHU_CHAT_ID", "")
    run_url = os.environ.get("RUN_URL", "")

    if not all([app_id, app_secret, chat_id]):
        print("Missing Feishu credentials, skipping")
        return

    # Find latest HTML report
    news_items = None
    for pattern in ["output/html/latest/current.html", "output/html/2026-06-16/*.html"]:
        for path in sorted(glob.glob(pattern), reverse=True):
            items = extract_news(path)
            if items:
                news_items = items
                break
        if news_items:
            break

    # Build message
    if news_items:
        lines = []
        for item in news_items[:20]:
            display = item[:50] + "..." if len(item) > 50 else item
            lines.append(f"• {display}")
        summary = "\n".join(lines)
        
        more = f"\n\n...还有 {len(news_items)-20} 条" if len(news_items) > 20 else ""
        text = f"📡 热点日报\n\n{summary}{more}\n\n查看详情: {run_url}"
    else:
        text = f"📡 热点日报\n暂无匹配热点\n查看详情: {run_url}"

    # Send to Feishu
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

    content = json.dumps({"text": text})
    msg = json.dumps({"receive_id": chat_id, "msg_type": "text", "content": content})

    req2 = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=msg.encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST"
    )
    resp2 = urllib.request.urlopen(req2, timeout=15)
    result = json.loads(resp2.read())
    if result.get("code") == 0:
        print(f"✅ Sent: {result['data']['message_id']}, items={len(news_items) if news_items else 0}")
    else:
        print(f"❌ Error: {result}")

if __name__ == "__main__":
    main()
