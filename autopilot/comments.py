#!/usr/bin/env python3
"""Read and answer comments on @uks_camper's own posts (Instagram Graph API).

    python3 autopilot/comments.py pending  [--days 14] [--max 30]  > pending.json
    python3 autopilot/comments.py reply    replies.json
    python3 autopilot/comments.py check

pending : new top-level comments on our recent posts that we have not answered yet,
          with the post caption for context. Our own comments and spam-looking ones
          are left out.
reply   : posts each {"comment_id", "text"} from replies.json as a reply, one by one,
          and records it in .claude/instagram/comments/replied.json so nothing is
          answered twice. Stops at the first error.
check   : confirms the token works and shows the account.

Token: the HTTPS proxy injects it for graph.instagram.com (saved as a network secret),
so this script sends a placeholder. Scopes needed: instagram_business_basic,
instagram_business_manage_comments.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://graph.instagram.com/v23.0"
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".claude/instagram/comments/replied.json"
SPAM = re.compile(r"(https?://|www\.|dm\s*me|팔로우\s*해?주|맞팔|선팔|협찬\s*문의|부업|수익|코인|무료\s*체험|promo|collab\?)", re.I)


def call(method, path, params=None):
    params = dict(params or {})
    url = f"{API}/{path}"
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer PLACEHOLDER_INJECTED_BY_PROXY"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"Instagram API {e.code}: {e.read().decode()[:500]}")


def paged(path, params, limit=200):
    out, res = [], call("GET", path, params)
    while True:
        out += res.get("data", [])
        nxt = res.get("paging", {}).get("next")
        if not nxt or len(out) >= limit:
            return out[:limit]
        with urllib.request.urlopen(urllib.request.Request(
                nxt, headers={"Authorization": "Bearer PLACEHOLDER_INJECTED_BY_PROXY"}), timeout=30) as r:
            res = json.loads(r.read().decode())


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"replied": {}}


def save_state(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1))


def me():
    return call("GET", "me", {"fields": "user_id,username"})


def pending(days=14, max_n=30):
    who = me()
    my_name = who.get("username", "")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    state = load_state()
    media = paged("me/media", {"fields": "id,caption,permalink,timestamp,comments_count", "limit": 25}, 50)
    out = []
    for m in media:
        ts = datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        if ts < since or not m.get("comments_count"):
            continue
        comments = paged(f"{m['id']}/comments",
                         {"fields": "id,text,username,timestamp,like_count,replies{username,text}", "limit": 50})
        for c in comments:
            if c["id"] in state["replied"] or c.get("username") == my_name:
                continue
            if any(r.get("username") == my_name for r in c.get("replies", {}).get("data", [])):
                continue
            text = c.get("text", "")
            out.append({
                "comment_id": c["id"], "username": c.get("username"), "text": text,
                "timestamp": c.get("timestamp"), "likes": c.get("like_count", 0),
                "looks_like_spam": bool(SPAM.search(text)),
                "post": {"permalink": m.get("permalink"), "caption": (m.get("caption") or "")[:600]},
            })
            if len(out) >= max_n:
                return out
    return out


def reply(path):
    items = json.loads(Path(path).read_text())
    state = load_state()
    done = 0
    for it in items:
        cid, text = it["comment_id"], it["text"].strip()
        if not text or cid in state["replied"]:
            continue
        res = call("POST", f"{cid}/replies", {"message": text})
        state["replied"][cid] = {"reply_id": res.get("id"), "text": text,
                                 "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "comment": it.get("comment_text", "")}
        save_state(state)
        done += 1
        print(f"replied {cid}: {text}")
        time.sleep(20)          # pace it like a person, not a burst
    print(f"{done} replies posted")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "check":
        print(json.dumps(me(), ensure_ascii=False))
    elif cmd == "pending":
        args = sys.argv[2:]
        days = int(args[args.index("--days") + 1]) if "--days" in args else 14
        mx = int(args[args.index("--max") + 1]) if "--max" in args else 30
        print(json.dumps(pending(days, mx), ensure_ascii=False, indent=1))
    elif cmd == "reply":
        reply(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
