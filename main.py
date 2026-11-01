import os, time, requests, threading
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
    # Use yes_sub_title first
    y=m.get("yes_sub_title","") or ""
    t=m.get("title","") or ""
    s=m.get("subtitle","") or ""
    raw=(y+" "+t+" "+s).lower()
    if "【entity-cruz azul¦canonical_name=Cruz Azul】" in raw:
        return "【entity-Cruz Azul¦canonical_name=Cruz Azul】"
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
    if "los angeles" in raw and "miami" in raw:
        return "LAFC vs Miami"
    if "【entity-palmeiras¦canonical_name=Palmeiras】" in raw:
        return "【entity-Palmeiras¦canonical_name=Palmeiras】"
    if "gremio" in raw:
        return "Gremio"
    if "miami" in raw:
        return "【entity-Inter Miami¦canonical_name=Inter Miami】"
    # fallback: take yes_sub before Over
    if "over" in y.lower():
        base=y.split("Over")[0].split("over")[0].strip()[:20]
        if len(base)>=3 and "KX" not in base.upper():
            return base
    return ""

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V51 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.now(timezone.utc)
        for m in markets:
            series=(m.get("series_ticker","") or "").upper()
            ev=(m.get("event_ticker","") or "").upper()
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
            # Soccer filter - V49 51 clean
            if "SOCCER" not in series and "SOCCER" not in ev:
                if not any(x in tl for x in ["【entity-cruz azul¦canonical_name=Cruz Azul】","tijuana","quilmes","lanus","vancouver","seattle","nashville","【entity-palmeiras¦canonical_name=Palmeiras】","gremio","miami","mls"]):
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
            if not (5 <= ya <= 95):
                continue
            exp=m.get("expiration_time","")
            try:
                if exp:
                    dt=datetime.fromisoformat(exp.replace("Z","+00:00"))
                    if dt < now_utc:
                        continue
            except:
                pass
            team=team_name(m)
            if not team or "CROSS" in team.upper() or "KX" in team.upper():
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":ev,"vol":m.get("volume",0),"exp":exp[5:16] if exp else ""})

        print(f"total {len(markets)} soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V51 FINAL CLEAN 51 Soccer Team 100% - Total {len(markets)} Soccer {len(soccer)}")

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
                o35=[x for x in lst if "3.5" in x["clean"]]
                if o25 and o35:
                    a=min(o25, key=lambda x: x["over"])
                    b=min(o35, key=lambda x: x["over"])
                    middles.append((a,b))

            middles=middles[:5]
            if middles:
                msg=f"PRE-MATCH MIDDLE {now} - {len(soccer)} Soccer Clean - {len(middles)} Middle\n(ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်)\n\n"
                for i,(a,b) in enumerate(middles,1):
                    msg+=f"{i}. {a['team']}\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c (Over 3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n   3 goals = both win 65%+ | Pre 2 side buy - 15' 0-0 Under add - 70' Jackpot Over\n\n"
                send(msg)
            else:
                top=soccer[:5]
                msg=f"PRE-MATCH {now} - {len(soccer)} Soccer Clean - Middle waiting\n"
                for s in top:
                    msg+=f"{s['team']} {s['clean']} {s['over']}c Exp {s['exp']}\n"
                send(msg)

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(3)
    send("V51 starting")
    while True:
        try:
            analyze()
            time.sleep(180)
        except Exception as e:
            print(e)
            time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V51 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
