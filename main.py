import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500].replace(" Kalshi"," KLSH")}, timeout=10)
    except:
        pass

def analyze():
    try:
        # ONLY 1000 - Deploy OK guarantee (V92 3000 OK, but 1000 safest)
        r=requests.get(f"{BASE}/markets", params={"status":"open","limit":1000}, timeout=15)
        if r.status_code==429:
            send(f"V95 429 - waiting 5min - Deploy OK but rate limited")
            return
        if r.status_code!=200:
            send(f"V95 API {r.status_code} - Deploy OK but API error")
            return
        ms=r.json().get("markets",[])
        
        utc_now=datetime.utcnow()
        soccer_pt=[]
        for m in ms:
            tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            # V92 PROVEN FILTER - found 163 in 3000
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
            ya=50
            real=False
            for v in [m.get("yes_ask"), m.get("yes_bid"), m.get("last_price")]:
                if v not in [None,0,""]:
                    try:
                        ya=int(float(v))
                        if ya>0:
                            real=True
                            break
                    except:
                        continue
            if ya<=0 or ya>=100:
                continue
            team="SOC"
            if " sassuolo" in tl: team="SAS"
            elif " fiorentina" in tl: team="FIO"
            elif " newcastle" in tl: team="NEW"
            elif " everton" in tl: team="EVE"
            elif " atalanta" in tl: team="ATA"
            elif " parma" in tl: team="PAR"
            soccer_pt.append({"team":team,"clean":"O2.5" if "2.5" in tl else "O3.5","over":ya,"under":100-ya,"exp_dt":exp_dt,"exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),"vol":m.get("volume",0) or 0,"real":real,"title":m.get("title","")})

        # Group
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
                if cost<=110:
                    middles.append({"title":g["title"],"exp_pst":g["exp_pst"],"o25":a,"o35":b,"cost":cost,"profit":200-cost})

        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V95 MINIMAL FIXED - Deploy OK!\nScanned {len(ms)} -> Soccer PT {len(soccer_pt)} (V92 filter proven)\nGames {len(games)} -> Middles {len(middles)} (cost<=110)\nNo spam!")

        if middles:
            msg=f"🔥 {len(middles)} MIDDLE FOUND! 🔥\n"
            for i,m in enumerate(middles[:5],1):
                tag_o="LIVE" if m["o25"]["real"] else "EST"
                tag_u="LIVE" if m["o35"]["real"] else "EST"
                msg+=f"{i}. {m['title'][:40]}\n   O2.5 {m['o25']['over']}c [{tag_o}] + U3.5 {m['o35']['under']}c [{tag_u}] Cost {m['cost']}c Profit 3goals +{m['profit']}c {m['exp_pst']} Vol {m['o25']['vol']}\n\n"
            send(msg)

    except Exception as e:
        send(f"V95 Error {str(e)[:200]} - Deploy OK but code error")

def bot_loop():
    time.sleep(3)
    send(f"V95 MINIMAL FIXED starting - 1000 markets + V92 filter - Deploy OK if you see this!")
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
        self.wfile.write(b"V95 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
