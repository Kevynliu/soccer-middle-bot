import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500]}, timeout=10)
    except:
        pass

def analyze():
    try:
        r=requests.get(f"{BASE}/markets", params={"status":"open","limit":1000}, timeout=15)
        if r.status_code!=200:
            send(f"V107 API {r.status_code}")
            return
        ms=r.json().get("markets",[])
        utc_now=datetime.utcnow()
        real=[]
        parlay=[]
        for m in ms:
            title=m.get("title","")
            tl=(title+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "2.5" not in tl and "3.5" not in tl: continue
            if "over" not in tl: continue
            if "goals scored" not in tl: continue
            if "edmonton" in tl or "ottawa" in tl or "both teams to score" in tl: continue
            exp=m.get("expiration_time","")
            try:
                exp_dt=datetime.fromisoformat(exp.replace("Z","")) if exp else None
                if not exp_dt or exp_dt < utc_now: continue
            except:
                continue
            ya=None
            real_flag=False
            for v in [m.get("yes_ask"), m.get("yes_bid"), m.get("last_price")]:
                if v not in [None,0,""]:
                    try:
                        ya=int(float(v))
                        if 0 < ya < 100:
                            real_flag=True
                            break
                    except:
                        continue
            if not ya or not (0 < ya < 100): continue
            entry={"over":ya,"under":100-ya,"exp_dt":exp_dt,"exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),"vol":m.get("volume",0) or 0,"real":real_flag,"title":title,"clean":"O2.5" if "2.5" in tl else "O3.5"}
            # Parlay = yes count >=2 or comma >=2
            if title.lower().count("yes")>=2 or title.count(",")>=2:
                parlay.append(entry)
            else:
                real.append(entry)

        # Real middles
        games={}
        for s in real:
            gkey=s["title"][:35]+s["exp_dt"].strftime("%m-%d %H")
            if gkey not in games:
                games[gkey]={"o25":[],"o35":[],"title":s["title"],"exp_pst":s["exp_pst"]}
            if "2.5" in s["clean"]:
                games[gkey]["o25"].append(s)
            else:
                games[gkey]["o35"].append(s)
        middles=[]
        for g in games.values():
            if g["o25"] and g["o35"]:
                a=min(g["o25"], key=lambda x: x["over"])
                b=min(g["o35"], key=lambda x: x["over"])
                cost=a["over"]+b["under"]
                if cost<=125:
                    middles.append({"title":g["title"],"exp_pst":g["exp_pst"],"o25":a,"o35":b,"cost":cost,"profit":200-cost})

        # Parlay middles
        p_games={}
        for s in parlay:
            gkey=s["title"][:40]+s["exp_dt"].strftime("%m-%d %H")
            if gkey not in p_games:
                p_games[gkey]={"o25":[],"o35":[],"title":s["title"],"exp_pst":s["exp_pst"]}
            if "2.5" in s["clean"]:
                p_games[gkey]["o25"].append(s)
            else:
                p_games[gkey]["o35"].append(s)
        p_middles=[]
        for g in p_games.values():
            if g["o25"] and g["o35"]:
                a=min(g["o25"], key=lambda x: x["over"])
                b=min
