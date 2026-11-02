import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

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
    for i in range(12):
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
        return "CZ"
    if "tijuana" in raw:
        return "TJ"
    if "quilmes" in raw:
        return "QL"
    if "lanus" in raw:
        return "LN"
    if "vancouver" in raw:
        return "VAN"
    if "seattle" in raw:
        return "SEA"
    if "nashville" in raw:
        return "NSH"
    if "palmeiras" in raw:
        return "PAL"
    if "gremio" in raw:
        return "GRE"
    if "los angeles" in raw and "miami" in raw:
        return "LA-MIA"
    if "miami" in raw:
        return "MIA"
    return ""

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V59 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.utcnow()
        for m in markets:
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
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
            exp_str=m.get("expiration_time","")
            if exp_str:
                try:
                    exp_dt=datetime.fromisoformat(exp_str.replace("Z",""))
                    if exp_dt < now_utc:
                        continue
                except:
                    pass
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
            team=team_name(m)
            if not team:
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"exp":exp_str[5:16] if exp_str else "","vol":m.get("volume",0)})

        print(f"total {len(markets)} soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V59 FINAL No Tag - Total {len(markets)} Soccer {len(soccer)} Clean - Tag fixed")

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

            middles=middles[:6]
            if middles:
                msg=f"MIDDLE {now} - {len(soccer)} games - {len(middles)} Middle\n\n"
                for i,(a,b) in enumerate(middles,1):
                    msg+=f"{i}. {a['team']}\n   O2.5 {a['over']}c + U3.5 {b['under']}c (O3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n   3 = both win | PRE 2 side | 15' U add | 70' JACKPOT O\n\n"
                send(msg)

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(3)
    send("V59 starting no tag")
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
        self.wfile.write(b"V59 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
