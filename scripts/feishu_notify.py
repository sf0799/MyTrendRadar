#!/usr/bin/env python3
"""Send TrendRadar notification to Feishu group chat."""
import json, os, urllib.request

def main():
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    chat_id = os.environ.get("FEISHU_CHAT_ID", "")
    run_url = os.environ.get("RUN_URL", "")

    if not all([app_id, app_secret, chat_id]):
        print("Missing Feishu credentials, skipping")
        return

    # Get access token
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
    text = f"📡 TrendRadar 热点日报\n查看详情: {run_url}"
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
