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

def clean_team_simple(ev, title):
    # ev like KXSOCCERMLS-2025-11-04-CRUZ-TIJ -> Cruz vs Tij
    if ev and "-" in ev:
        parts=ev.split("-")
        # last 2 are team codes if SOCCER
        if len(parts) >= 2:
            t1=parts[-2]
            t2=parts[-1]
            # Skip CROSSCATEGORY
            if "CROSS" in t1.upper() or "CROSS" in t2.upper():
                return ""
            # Map common
            m={"CRUZ":"Cruz Azul","TIJ":"Tijuana","VAN":"Vancouver","SEA":"Seattle","NYRB":"NY RB","LAFC":"LAFC","MIA":"Miami","LANUS":"Lanus","QUILM":"Quilmes","CRU":"Cruzeiro"}
            t1=m.get(t1.upper(), t1)
            t2=m.get(t2.upper(), t2)
            if len(t1)>=2 and len(t2)>=2:
                return f"{t1} vs {t2}"
    # Fallback title first team
    t=title.split("Over")[0].replace("yes","").replace("no","").replace(",","").strip()[:30]
    return t if len(t)>=3 else "Soccer"

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V47 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.now(timezone.utc)
        for m in markets:
            series=(m.get("series_ticker","") or "").upper()
            ev=(m.get("event_ticker","") or "")
            ev_up=ev.upper()
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
            # CrossCategory - check Ticker and Series too
            if "CROSSCATEGORY" in series or "CROSSCATEGORY" in ev_up or "CROSSCATEGORY" in title.upper():
                continue
            if "CROSS" in series and "CATEGORY" in series:
                continue
            if "both teams to score" in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl or "lendeborg" in tl or "austin reaves" in tl:
                continue
            if "wins by more than" in tl:
                continue
            if "over" not in tl or "goals scored" not in tl:
                continue
            if "2.5" not in tl and "3.5" not in tl:
                continue
            # Soccer only
            if "SOCCER" not in series and "SOCCER" not in ev_up:
                if not any(x in tl for x in ["mls","cruz azul","tijuana","vancouver","seattle","quilmes","lanus"]):
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
            team=clean_team_simple(ev, m.get("title","") or m.get("yes_sub_title",""))
            if not team:
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":ev,"vol":m.get("volume",0),"exp":exp[5:16] if exp else ""})

        print(f"total {len(markets)} soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V47 FINAL CLEAN Live - CrossCategory Ticker ဖျက် - Total {len(markets)} Soccer {len(soccer)}")

        if soccer:
            by_ev={}
            for s in soccer:
                ev=s["ev"]
                if ev not in by_ev:
                    by_ev[ev]=[]
                by_ev[ev].append(s)

            middles=[]
            for ev, lst in by_ev.items():
                o25=[x for x in lst if "2.5" in x["clean"]]
                o35=[x for x in lst if "3.5" in x["clean"]]
                if o25 and o35:
                    middles.append((o25[0],o35[0]))

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
    send("V47 starting")
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
        self.wfile.write(b"V47 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
