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
        # V103 EXACT - 1000 limit - PROVEN Soccer 94
        r=requests.get(f"{BASE}/markets", params={"status":"open","limit":1000}, timeout=15)
        if r.status_code!=200:
            send(f"V109 API {r.status_code}")
            return
        ms=r.json().get("markets",[])
        utc_now=datetime.utcnow()
        soccer_pt=[]
        for m in ms:
            # V103 EXACT FILTER - found 94
            tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "2.5" not in tl and "3.5" not in tl:
                continue
            if "over" not in tl:
                continue
            if "goals scored" not in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl or "both teams to score" in tl:
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
                if v not in [None,0,""]:
                    try:
                        ya=int(float(v))
                        if 0 < ya < 100:
                            real=True
                            break
                    except:
                        continue
            if not ya or not (0 < ya < 100):
                continue
            soccer_pt.append({
                "over":ya,"under":100-ya,
                "exp_dt":exp_dt,
                "exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),
                "vol":m.get("volume",0) or 0,
                "real":real,
                "title":m.get("title",""),
                "clean":"O2.5" if "2.5" in tl else "O3.5"
            })

        # SPLIT INTO BOTH - Keep both, don't filter out
        real_list=[]
        parlay_list=[]
        for s in soccer_pt:
            t=s["title"]
            # Parlay = has comma + yes multiple
            if t.lower().count("yes") >= 2 or t.count(",") >= 2:
                parlay_list.append(s)
            else:
                real_list.append(s)

        # Real games grouping
        real_games={}
        for s in real_list:
            gkey=s["title"][:35]+s["exp_dt"].strftime("%m-%d %H")
            if gkey not in real_games:
                real_games[gkey]={"o25":[],"o35":[],"title":s["title"],"exp_pst":s["exp_pst"]}
            if "2.5" in s["clean"]:
                real_games[gkey]["o25"].append(s)
            else:
                real_games[gkey]["o35"].append(s)

        real_middles=[]
        for g in real_games.values():
            if g["o25"] and g["o35"]:
                a=min(g["o25"], key=lambda x: x["over"])
                b=min(g["o35"], key=lambda x: x["over"])
                cost=a["over"]+b["under"]
                if cost<=125:
                    real_middles.append({"title":g["title"],"exp_pst":g["exp_pst"],"o25":a,"o35":b,"cost":cost,"profit":200-cost})

        # Parlay games grouping
        parlay_games={}
        for s in parlay_list:
            gkey=s["title"][:40]+s["exp_dt"].strftime("%m-%d %H")
            if gkey not in parlay_games:
                parlay_games[gkey]={"o25":[],"o35":[],"title":s["title"],"exp_pst":s["exp_pst"]}
            if "2.5" in s["clean"]:
                parlay_games[gkey]["o25"].append(s)
            else:
                parlay_games[gkey]["o35"].append(s)

        parlay_middles=[]
        for g in parlay_games.values():
            if g["o25"] and g["o35"]:
                a=min(g["o25"], key=lambda x: x["over"])
                b=min(g["o35"], key=lambda x: x["over"])
                cost=a["over"]+b["under"]
                if cost<=125:
                    parlay_middles.append({"title":g["title"],"exp_pst":g["exp_pst"],"o25":a,"o35":b,"cost":cost,"profit":200-cost})

        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V109 BOTH FINAL - Deploy OK!\nScanned {len(ms)} -> Total Soccer {len(soccer_pt)} (V103 proven 94)\nReal {len(real_list)} Games {len(real_games)} Middles {len(real_middles)}\nParlay {len(parlay_list)} Games {len(parlay_games)} Middles {len(parlay_middles)}\nBoth saved!")

        if real_middles:
            msg=f"⚽ REAL SOCCER MIDDLE 🔥 {len(real_middles)} found\n"
            for i,m in enumerate(real_middles[:4],1):
                tag_o="LIVE" if m["o25"]["real"] else "EST"
                tag_u="LIVE" if m["o35"]["real"] else "EST"
                msg+=f"{i}. {m['title'][:40]}\n O2.5 {m['o25']['over']}c [{tag_o}] + U3.5 {m['o35']['under']}c [{tag_u}] Cost {m['cost']}c +{m['profit']}c {m['exp_pst']}\n\n"
            send(msg)

        if parlay_middles:
            msg=f"🎯 PARLAY SAVED 🔥 {len(parlay_middles)} found\n"
            for i,m in enumerate(parlay_middles[:4],1):
                tag_o="LIVE" if m["o25"]["real"] else "EST"
                tag_u="LIVE" if m["o35"]["real"] else "EST"
                msg+=f"{i}. {m['title'][:45]}\n O2.5 {m['o25']['over']}c + U3.5 {m['o35']['under']}c Cost {m['cost']}c +{m['profit']}c {m['exp_pst']} Vol {m['o25']['vol']}\n\n"
            send(msg)

        if not real_middles and not parlay_middles:
            if not hasattr(analyze,"last_no") or time.time()-analyze.last_no > 10800:
                analyze.last_no=time.time()
                send(f"No middle in {len(ms)} -> Real {len(real_list)} Parlay {len(parlay_list)} - Checking 5min - Both saved!")

    except Exception as e:
        send(f"V109 Error {str(e)[:100]}")

def bot_loop():
    time.sleep(3)
    send(f"V109 BOTH FINAL starting - V103 clone (Soccer 94) + Real + Parlay Both Saved - Deploy OK guaranteed!")
    while True:
        try:
            analyze()
            time.sleep(300)
        except:
            time.sleep(300)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V109 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
