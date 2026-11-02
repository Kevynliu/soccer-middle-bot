import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=15)
    except:
        pass

def analyze():
    try:
        all_m=[]
        cur=None
        for i in range(12):
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
                time.sleep(0.3)
            except:
                break

        soccer=[]
        now_utc=datetime.utcnow()
        for m in all_m:
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
            if "both teams to score" in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl:
                continue
            if "wins by more than" in tl:
                continue
            if "over" not in tl or "goals scored" not in tl:
                continue
            if "2.5" not in tl and "3.5" not in tl:
                continue
            exp=m.get("expiration_time","")
            if exp:
                try:
                    if datetime.fromisoformat(exp.replace("Z","")) < now_utc:
                        continue
                except:
                    pass
            ya=None
            for v in [m.get("yes_ask"), m.get("yes_bid"), m.get("last_price")]:
                if v not in [None,0,"0",""]:
                    try:
                        ya=int(float(v))
                        break
                    except:
                        continue
            if ya is None:
                ya=50
            if not (5 <= ya <= 95):
                continue
            txt=tl
            team=""
            if "newcastle" in txt and "everton" in txt:
                team="NEW-EVE"
            elif "newcastle" in txt:
                team="NEW"
            elif "everton" in txt:
                team="EVE"
            elif "cruz" in txt:
                team="CZ"
            elif "tijuana" in txt:
                team="TJ"
            elif "vancouver" in txt:
                team="VAN"
            elif "seattle" in txt:
                team="SEA"
            elif "nashville" in txt:
                team="NSH"
            elif "miami" in txt:
                team="MIA"
            elif "atalanta" in txt:
                team="ATA-PAR"
            elif "parma" in txt:
                team="ATA-PAR"
            elif "lorient" in txt:
                team="LOR-BRE"
            elif "sassuolo" in txt or "fiorentina" in txt:
                team="SAS-FIO"
            elif " vs " in txt:
                team="SOC"
            if not team:
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"exp":exp[5:16] if exp else "","vol":m.get("volume",0) or 0,"ticker":m.get("ticker","")})

        print(f"V66 total {len(all_m)} soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V66 Minimal Clean Deploy - Total {len(all_m)} Soccer {len(soccer)} - No OB, 12 batch, EST Middle")

        if soccer:
            by_team={}
            for s in soccer:
                k=s["team"]
                if k not in by_team:
                    by_team[k]=[]
                by_team[k].append(s)

            middles=[]
            for team, lst in by_team.items():
                o25=[x for x in lst if "2.5" in x["clean"]]
                o35=
