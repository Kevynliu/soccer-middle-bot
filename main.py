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

def get_markets(total=5000):
    all_ms=[]
    cursor=None
    while len(all_ms) < total:
        try:
            p={"status":"open","limit":1000}
            if cursor:
                p["cursor"]=cursor
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code!=200:
                break
            d=r.json()
            batch=d.get("markets",[])
            if not batch:
                break
            all_ms.extend(batch)
            cursor=d.get("cursor")
            if not cursor or len(all_ms)>=total:
                break
            time.sleep(0.5)
        except:
            break
    return all_ms

def analyze():
    try:
        ms=get_markets(total=5000)
        if not ms:
            return
        utc_now=datetime.utcnow()
        real=[]
        parlay=[]
        
        for m in ms:
            title=m.get("title","")
            tl=(title+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "2.5" not in tl and "3.5" not in tl: continue
            if "over" not in tl: continue
            if "goals scored" not in tl: continue
            if "edmonton" in tl or "ottawa" in tl: continue
            
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
            
            # V110 shows first 1000 all parlay - need to go beyond
            # Parlay = yes count >=2 or comma >=2
            if title.lower().count("yes")>=2 or title.count(",")>=2:
                parlay.append(entry)
            else:
                real.append(entry)

        # Real middle
        real_games={}
        for s in real:
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

        # Parlay middle
        parlay_games={}
        for s in parlay:
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
            send(f"V111 BOTH - Deploy OK!\nScanned {len(ms)} -> Real Single {len(real)} Games {len(real_games)} Middles {len(real_middles)}\nParlay {len(parlay)} Games {len(parlay_games)} Middles {len(parlay_middles)}\nFirst 1000 all parlay (V110), real beyond 1000 - Both saved!")

        if real_middles:
            msg=f"⚽ REAL SINGLE GAME MIDDLE 🔥 {len(real_middles)} found\n"
            for i,m in enumerate(real_middles[:4],1):
                tag_o="LIVE" if m["o25"]["real"] else "EST"
                tag_u="LIVE" if m["o35"]["real"] else "EST"
                msg+=f"{i}. {m['title'][:42]}\n O2.5 {m['o25']['over']}c [{tag_o}] + U3.5 {m['o35']['under']}c [{tag_u}] Cost {m['cost']}c +{m['profit']}c {m['exp_pst']}\n\n"
            send(msg)

        if parlay_middles:
            msg=f"🎯 PARLAY SAVED 🔥 {len(parlay_middles)} found\n"
            for i,m in enumerate(parlay_middles[:4],1):
                tag_o="LIVE" if m["o25"]["real"] else "EST"
                tag_u="LIVE" if m["o35"]["real"] else "EST"
                msg+=f"{i}. {m['title'][:45]}\n O2.5 {m['o25']['over']}c + U3.5 {m['o35']['under']}c Cost {m['cost']}c +{m['profit']}c {m['exp_pst']}\n\n"
            send(msg)

        if not real_middles and not parlay_middles:
            if not hasattr(analyze,"last_no") or time.time()-analyze.last_no > 10800:
                analyze.last_no=time.time()
                send(f"No middle in {len(ms)} -> Real {len(real)} Parlay {len(parlay)} - Both saved, checking 5min")

    except Exception as e:
        send(f"V111 Error {str(e)[:100]}")

def bot_loop():
    time.sleep(3)
    send(f"V111 BOTH starting - 5000 scan + Real beyond 1000 + Parlay Both Saved - Deploy OK!")
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
        self.wfile.write(b"V111 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
