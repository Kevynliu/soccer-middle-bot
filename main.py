import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500].replace(" Kalshi","KLSH")}, timeout=12)
    except:
        pass

def analyze():
    try:
        # ONLY 400 markets - Deploy OK guarantee
        p={"status":"open","limit":400}
        r=requests.get(f"{BASE}/markets", params=p, timeout=10)
        if r.status_code!=200:
            send(f"V83 Test API {r.status_code}")
            return
        ms=r.json().get("markets",[])

        utc_now=datetime.utcnow()
        pst_now=utc_now - timedelta(hours=7)
        tomorrow_pst=pst_now + timedelta(days=1)
        tomorrow_start_pst=datetime(tomorrow_pst.year, tomorrow_pst.month, tomorrow_pst.day, 0,0,0)
        tomorrow_end_pst=tomorrow_start_pst + timedelta(days=1)
        tomorrow_start_utc=tomorrow_start_pst + timedelta(hours=7)
        tomorrow_end_utc=tomorrow_end_pst + timedelta(hours=7)
        tomorrow_str=tomorrow_start_pst.strftime("%m-%d")

        soccer_pt=[]
        for m in ms:
            tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            # FIXED: must have goals scored + over 2.5/3.5 = Soccer only, no NBA
            if "2.5" not in tl and "3.5" not in tl:
                continue
            if "over" not in tl:
                continue
            if "goals scored" not in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl or "both teams to score" in tl or "wins by more than" in tl:
                continue
            exp=m.get("expiration_time","")
            try:
                exp_dt=datetime.fromisoformat(exp.replace("Z","")) if exp else None
                if not exp_dt or exp_dt < utc_now:
                    continue
            except:
                continue

            ya=None
            real=False
            for v in [m.get("yes_ask"), m.get("yes_bid"), m.get("last_price")]:
                if v not in [None,0,"0",""]:
