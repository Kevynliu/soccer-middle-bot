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
        return "CruzAzul"
    if "【entity-tijuana¦canonical_name=Club Tijuana】" in raw:
        return "【entity-Tijuana¦canonical_name=Club Tijuana】"
    if "quilmes" in raw:
        return "Quilmes"
    if "【entity-lanus¦canonical_name=Club Atlético Lanús】" in raw:
        return "【entity-Lanus¦canonical_name=Club Atlético Lanús】"
    if "【entity-vancouver¦canonical_name=Vancouver Whitecaps FC】" in raw:
        return "【entity-Vancouver¦canonical_name=Vancouver Whitecaps FC】"
    if "【entity-seattle¦canonical_name=Seattle Sounders FC】" in raw:
        return "【entity-Seattle¦canonical_name=Seattle Sounders FC】"
    if "【entity-nashville¦canonical_name=Nashville SC】" in raw:
        return "【entity-Nashville¦canonical_name=Nashville SC】"
    if "【entity-palmeiras¦canonical_name=Palmeiras】" in raw:
        return "【entity-Palmeiras¦canonical_name=Palmeiras】"
    if "【entity-gremio¦canonical_name=Grêmio FBPA】" in raw:
        return "【entity-Gremio¦canonical_name=Grêmio FBPA】"
    if "los angeles" in raw and "miami" in raw:
        return "LAFCvsMIA"
    if "miami" in raw:
        return "MiamiTeam"
    return ""

prev_prices={}
def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V56 {now}")
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
            # Ignore finished - exp < now
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
            # Live tracking
            key=m.get("ticker","")+team
            old=prev_prices.get(key)
            if old is not None and abs(old-ya) >= 15:
                if old >= 70 and ya <= 50:
                    send(f"LIVE JACKPOT {now} - {team} {clean} {old}c -> {ya}c DOWN! BUY Over NOW for Middle!")
                elif old <= 35 and ya >= 65:
                    send(f"LIVE SPIKE {now} - {team} {clean} {old}c -> {ya}c UP! Goals early - Hold Under!")
            prev_prices[key]=ya
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"exp":exp_str[5:16] if exp_str else ""})

        print(f"total {len(markets)} soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V56 FINAL Live Tracking - Total {len(markets)} Soccer {len(soccer)} Clean - Finished filter + Live jackpot")

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
                msg=f"PRE-MATCH MIDDLE {now} - {len(soccer)} Soccer - {len(middles)} Middle (Finished filtered)\n\n"
                for i,(a,b) in enumerate(middles,1):
                    msg+=f"{i}. {a['team']}\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c (Over 3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n   3 goals = both win | PRE 2 side | 15' 0-0 Under add | 70' Jackpot Over\n\n"
                send(msg)

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(3)
    send("V56 starting live tracking")
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
        self.wfile.write(b"V56 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
