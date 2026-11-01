import os, time, requests, threading, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=20)
    except:
        pass

def get_all():
    all_m=[]
    cur=None
    for i in range(25):
        try:
            p={"status":"open","limit":400}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=25)
            if r.status_code!=200:
                continue
            data=r.json()
            ms=data.get("markets",[])
            all_m.extend(ms)
            cur=data.get("cursor")
            if not cur:
                break
            time.sleep(0.5)
        except:
            break
    return all_m

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V40 {now}")
    markets=get_all()
    soccer=[]
    now_utc=datetime.now(timezone.utc)
    for m in markets:
        title_raw=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
        tl=title_raw.lower()
        if "edmonton" in tl or "ottawa" in tl or "draisaitl" in tl:
            continue
        if "wins by more than" in tl:
            continue
        if "over" not in tl or "goals scored" not in tl:
            continue
        if not re.search(r"over\s+(2\.5|3\.5)\s+goals\s+scored", tl):
            continue
        ya=None
        for k in ["yes_ask","yes_bid","last_price"]:
            v=m.get(k)
            if v not in [None,0,"0",""]:
                try:
                    ya=int(float(v))
                    break
                except:
                    continue
        if ya is None:
            ya=50
        if not (10 <= ya <= 90):
            continue
        exp_str=m.get("expiration_time","")
        try:
            if exp_str:
                dt=datetime.fromisoformat(exp_str.replace("Z","+00:00"))
                if dt < now_utc:
                    continue
        except:
            pass
        # Team clean simple
        t=m.get("yes_sub_title","") or m.get("title","")
        t=t.replace("yes","").replace("no","")
        t=t.split("Over")[0]
        t=t.replace(",","").strip()[:40]
        if len(t) < 3:
            t=m.get("event_ticker","")[:20]
        clean_match=re.search(r"Over\s+\d+\.5\s+goals\s+scored", title_raw, re.I)
        clean=clean_match.group(0) if clean_match else "Over"
        soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":t,"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"exp":exp_str[5:16] if exp_str else ""})
    print(f"Total {len(markets)} Soccer {len(soccer)}")
    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"V40 FINAL - Deploy fix - 410 middle - Soccer 2.5/3.5")
    if soccer:
        from collections import defaultdict
        by_ev=defaultdict(list)
        for s in soccer:
           
