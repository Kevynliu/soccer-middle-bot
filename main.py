import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta

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
    for i in range(15):
        try:
            p={"status":"open","limit":400}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
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

def team_name(m):
    y=(m.get("yes_sub_title","") or "").lower()
    t=(m.get("title","") or "").lower()
    raw=y+" "+t
    if "cruz" in raw:
        return "【entity-CruzAzul¦canonical_name=cruz azul】"
    if "tijuana" in raw:
        return "Tijuana"
    if "quilmes" in raw:
        return "Quilmes"
    if "lanus" in raw:
        return "Lanus"
    if "vancouver" in raw:
        return "Vancouver"
    if "seattle" in raw:
        return "Seattle"
    if "nashville" in raw:
        return "Nashville"
    if "【entity-palmeiras¦canonical_name=Palmeiras】" in raw:
        return "【entity-Palmeiras¦canonical_name=Palmeiras】"
    if "gremio" in raw:
        return "Gremio"
    if "los angeles" in raw and "miami" in raw:
        return "LAFCvsMIA"
    if "miami" in raw:
        return "Miami"
    return ""

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V54 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.now(timezone.utc)
        limit_7d=now_utc+timedelta(days=7)
        for m in markets:
            series=(m.get("series_ticker","") or "").upper()
            ev=(m.get("event_ticker","") or "").upper()
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
            if "SOCCER" not in series and "SOCCER" not in ev:
                if not any(x in tl for x in ["cruz","tijuana","quilmes","lanus","vancouver","seattle","nashville","【entity-palmeiras¦canonical_name=Palmeiras】","gremio","miami","mls"]):
                    continue
            if "both teams to score" in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl or "lendeborg" in tl or "austin reaves" in tl or "yaxel" in tl:
                continue
            if "wins by more than" in tl:
                continue
            if "over" not in tl or "goals scored" not in tl:
                continue
            if "2.5" not in tl and "3.5" not in tl:
                continue
            ya=None
            yb=m.get("yes_bid")
            ya_raw=m.get("yes_ask")
            lp=m.get("last_price")
            try:
                if ya_raw is not None and yb is not None and ya_raw!=0 and yb!=0:
                    ya=int((float(ya_raw)+float(yb))/2)
                elif ya_raw is not None and ya_raw!=0:
                    ya=int(float(ya_raw))
                elif yb is not None and yb!=0:
                    ya=int(float(yb))
                elif lp is not None and lp!=0:
                    ya=int(float(lp))
            except:
                pass
            if ya is None:
                ya=50
            if not (5 <= ya <= 95):
                continue
            exp=m.get("expiration_time","")
            exp_dt=None
            try:
                if exp:
                    exp_dt=datetime.fromisoformat(exp.replace("Z","+00:00"))
                    if exp_dt < now_utc:
                        continue
                    if exp_dt > limit_7d:
                        continue
            except:
                pass
            team=team_name(m)
            if not team:
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            vol=m.get("volume",0) or 0
            soccer.append({"over":ya,"under":100-ya,"clean":
