import os, time, requests, threading, re
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

def clean_team(raw_title, ev):
    # raw_title like "Cruz Azul vs Tijuana Over 2.5 goals scored" -> "Cruz Azul vs Tijuana"
    # or "Both Teams To Score Cruz Azul Both Teams To Score Yes" -> filter out earlier
    t=raw_title or ""
    # Remove yes/no
    t=re.sub(r"^(yes|no)\s+", "", t, flags=re.I)
    # Take before Over
    t=t.split("Over")[0]
    t=t.split("Both Teams")[0]
    t=t.replace(",","").replace("  "," ").strip()
    # If still messy like "KXMVECROSSCATEGORY-S", use ev
    if "CROSSCATEGORY" in t.upper() or len(t) < 5 or "KX" in t[:2]:
        # ev like KXSOCCER-2025-11-04-CRUZ-TIJ
        if ev and "-" in ev:
            parts=ev.split("-")
            if len(parts) >= 2:
                # last two parts are team codes
                t1=parts[-2]
                t2=parts[-1]
                # Map codes
                mapping={"CRUZ":"Cruz Azul","TIJ":"Tijuana","VAN":"Vancouver","SEA":"Seattle","NYRB":"NY RB","ATL":"Atlanta","NSH":"Nashville"}
                t1=mapping.get(t1.upper(), t1)
                t2=mapping.get(t2.upper(), t2)
                return f"{t1} vs {t2}"
        return ev[:25] if ev else "Soccer Match"
    return t[:40]

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V43 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.now(timezone.utc)
        for m in markets:
            title_raw=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title_raw.lower()
            # Filter
            if "croscategory" in tl or "crosscategory" in tl:
                continue
            if "both teams to score" in tl or "btts" in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl:
                continue
            if "wins by more than" in tl:
                continue
            if "over" not in tl or "goals scored" not in tl:
                continue
            if "2.5" not in tl and "3.5" not in tl:
                continue
            # Price - skip Vol 0 fake 50c if possible, try get real
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
                continue # Skip fake 50c
            if not (15 <= ya <= 85):
                continue
            exp=m.get("expiration_time","")
            try:
                if exp:
                    dt=datetime.fromisoformat(exp.replace("Z","+00:00"))
                    if dt < now_utc:
                        continue
            except:
                pass
            ev=m.get("event_ticker","")
            team=clean_team(m.get("title","") or m.get("yes_sub_title",""), ev)
            clean="Over 2.5 goals" if "2.5" in tl else "Over 3.5 goals"
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":ev,"vol":m.get("volume",0),"exp":exp[5:16] if exp else ""})

        print(f"total {len(markets)} soccer clean {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V43 FINAL CLEAN Live - BTTS + CrossCategory ဖျက် - Total {len(markets)} Soccer {len(soccer)}")

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
                msg=f"PRE-MATCH MIDDLE {now} - {len(soccer)} Soccer 2.5/3.5 Clean - {len(middles)} Middle\n(ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်)\n\n"
                for i,(a,b) in enumerate(middles,1):
                    msg+=f"{i}. {a['team']}\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c (Over 3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n   3 goals = both win Win 65%+ | Pre 2 side buy - 15' 0-0 Under add - 70' Jackpot Over\n\n"
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
    send("V43 starting")
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
        self.wfile.write(b"V43 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
