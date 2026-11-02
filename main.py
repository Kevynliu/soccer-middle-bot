import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500].replace(" Kalshi","KLSH")}, timeout=15)
    except:
        pass

def get_all(batches=5):
    all_m=[]
    cur=None
    for i in range(batches):
        try:
            p={"status":"open","limit":400}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=12)
            if r.status_code!=200:
                break
            data=r.json()
            ms=data.get("markets",[])
            if not ms:
                break
            all_m.extend(ms)
            cur=data.get("cursor")
            if not cur:
                break
            time.sleep(0.5)
        except:
            break
    return all_m

def analyze():
    try:
        markets=get_all(5)  # 2000 markets
        utc_now=datetime.utcnow()
        pst_now=utc_now - timedelta(hours=7)
        tomorrow_pst=pst_now + timedelta(days=1)
        tomorrow_start_pst=datetime(tomorrow_pst.year, tomorrow_pst.month, tomorrow_pst.day, 0,0,0)
        tomorrow_end_pst=tomorrow_start_pst + timedelta(days=1)
        tomorrow_start_utc=tomorrow_start_pst + timedelta(hours=7)
        tomorrow_end_utc=tomorrow_end_pst + timedelta(hours=7)
        tomorrow_str=tomorrow_start_pst.strftime("%m-%d")
        today_str=pst_now.strftime("%m-%d")

        soccer_pt=[]
        for m in markets:
            tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            # FIXED FILTER - must have goals scored + over 2.5/3.5
            if "2.5" not in tl and "3.5" not in tl:
                continue
            if "over" not in tl:
                continue
            if "goals scored" not in tl:  # Soccer only
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
                    try:
                        ya=int(float(v))
                        real=True
                        break
                    except:
                        continue
            if ya is None:
                ya=50

            team="SOC"
            if "sassuolo" in tl or "fiorentina" in tl:
                team="SAS-FIO"
            elif "atalanta" in tl or "parma" in tl:
                team="ATA-PAR"
            elif "newcastle" in tl or "everton" in tl:
                team="NEW-EVE"
            elif "cruz" in tl:
                team="CZ"
            elif "vancouver" in tl:
                team="VAN"

            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer_pt.append({"over":ya,"clean":clean,"team":team,"exp_dt":exp_dt,"exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H
