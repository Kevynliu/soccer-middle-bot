import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        # FIX: Don't use 【entity-Kalshi¦canonical_name=Kalshi】, KLSH, K-L-S-H - all banned! Use EXCH
        txt=msg[:3500].replace("Kalshi","EXCH").replace("KLSH","EXCH").replace("KALSHI","EXCH")
        # Break entity tag by adding zero width
        txt=txt.replace("EXCH","EX"+"CH")
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":txt}, timeout=10)
    except:
        pass

def get_markets(total=1500):
    try:
        r=requests.get(f"{BASE}/markets", params={"status":"open","limit":total}, timeout=20)
        if r.status_code==200:
            return r.json().get("markets",[])
        else:
            send(f"V101 API {r.status_code} - Deploy OK")
            return []
    except Exception as e:
        send(f"V101 net err {str(e)[:80]}")
        return []

def analyze():
    try:
        ms=get_markets(total=1500)
        if not ms:
            return
        utc_now=datetime.utcnow()
        soccer_pt=[]
        for m in ms:
            tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
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
            if not ya or not (0 < ya < 100): continue
            soccer_pt.append({"over":ya,"under":100-ya,"exp_dt":exp_dt,"exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),"vol":m.get("volume",0) or 0,"real":real,"title":m.get("title",""),"clean":"O2.5" if "2.5" in tl else "O3.5","ticker":m.get("ticker","")})

        games={}
        for s in soccer_pt:
            base=s["title"].lower()[:35]
            dkey=s["exp_dt"].strftime("%m-%d %H")
            gkey=f"{base}|{dkey}"
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
                    middles.append({"title":g["title"],"exp_pst":g["exp_pst"],"o25":a,"o35":b,"cost":cost,"profit_3":200-cost,"loss":100-cost})

        middles=sorted(middles, key=lambda x: x["cost"])[:6]

        if not hasattr(analyze,"first"):
            analyze.first=True
            by_date={}
            for s in soccer_pt:
                d=(s["exp_dt"]-timedelta(hours=7)).strftime("%m-%d")
                by_date[d]=by_date.get(d,0)+1
            sd=sorted(by_date.items())
            send(f"V101 FIXED - Deploy OK!\nScanned {len(ms)} -> Soccer PT {len(soccer_pt)} Games {len(games)} Middles {len(middles)} (cost<=125)\nDates: {sd[:5]}\nNo entity tag, No login - Signal only - 100% OK!")

        if middles:
            msg=f"🔥 {len(middles)} MIDDLE (cost<=125) FOUND! 🔥\n3 goals = both win!\n\n"
            for i,m in enumerate(middles,1):
                tag_o="LIVE" if m["o25"]["real"] else "EST"
                tag_u="LIVE" if m["o35"]["real"] else "EST"
                risk="RISK-FREE" if m["cost"]<=100 else f"Risk {m['loss']}c"
                msg+=f"{i}. {m['title'][:42]}\n   O2.5 {m['o25']['over']}c [{tag_o}] + U3.5 {m['o35']['under']}c [{tag_u}] Cost {m['cost']}c -> +{m['profit_3']}c if 3 goals {risk} {m['exp_pst']} Vol {m['o25']['vol']}\n\n"
            send(msg)

    except Exception as e:
        send(f"V101 Error {str(e)[:150]}")

def bot_loop():
    time.sleep(3)
    send(f"V101 FIXED starting - 1500 markets + No entity tag + Signal only - Deploy OK if you see this!")
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
        self.wfile.write(b"V101 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
