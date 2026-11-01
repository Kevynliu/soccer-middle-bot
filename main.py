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

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V42 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.now(timezone.utc)
        for m in markets:
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
            if "edmonton" in tl or "ottawa" in tl:
                continue
            if "wins by more than" in tl:
                continue
            if "over" not in tl or "goals scored" not in tl:
                continue
            # Only 2.5 and 3.5
            if "2.5" not in tl and "3.5" not in tl:
                continue
            # Price
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
            # ပွဲပြီးတာ မပါ
            exp=m.get("expiration_time","")
            try:
                if exp:
                    dt=datetime.fromisoformat(exp.replace("Z","+00:00"))
                    if dt < now_utc:
                        continue
            except:
                pass
            # Team clean
            team=m.get("yes_sub_title","") or m.get("title","")
            team=team.replace("yes","").replace("no","")
            team=team.split("Over")[0].replace(",","").strip()[:40]
            if len(team) < 3:
                team=m.get("event_ticker","")[:20]
            # Clean Over text
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"exp":exp[5:16] if exp else ""})

        print(f"total {len(markets)} soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V42 FINAL MIDDLE Live - Total {len(markets)} Soccer {len(soccer)} - Deploy ok")

        if soccer:
            # Group by event
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
                msg=f"PRE-MATCH MIDDLE {now} - {len(soccer)} Soccer 2.5/3.5 - {len(middles)} Middle\n(ပွဲပြီးတာ မပါ, လက္ရွိ+ေနာက္လာမယ့္)\n\n"
                for i,(a,b) in enumerate(middles,1):
                    msg+=f"{i}. {a['team']}\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c (Over 3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n   3 goals = both win Win 65%+\n   Strategy: Pre-match 2 side buy - 15' 0-0 Under add - 70' Jackpot Over\n\n"
                send(msg)
            else:
                top=soccer[:5]
                msg=f"PRE-MATCH {now} - {len(soccer)} Soccer - Middle waiting\n"
                for s in top:
                    msg+=f"{s['team']} {s['clean']} {s['over']}c Exp {s['exp']}\n"
                send(msg)

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(3)
    send("V42 starting")
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
        self.wfile.write(b"V42 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
