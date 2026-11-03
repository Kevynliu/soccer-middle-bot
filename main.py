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
            time.sleep(0.6)
        except Exception as e:
            break
    return all_ms

def analyze():
    try:
        ms=get_markets(total=5000)
        if not ms:
            return
        utc_now=datetime.utcnow()
        # V103 clone logic - NO price filter for counting
        all_soccer=[]
        real=[]
        parlay=[]
        no_price=0
        
        for m in ms:
            title=m.get("title","")
            tl=(title+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "goals scored" not in tl: continue
            if "over" not in tl: continue
            if "2.5" not in tl and "3.5" not in tl and "1.5" not in tl: continue
            
            all_soccer.append(m)
            
            # Try get price - ANY field
            ya=None
            for k in ["yes_ask","yes_bid","last_price","yes_ask_dollars","price"]:
                v=m.get(k)
                if v not in [None,"",0]:
                    try:
                        if isinstance(v,str):
                            v=float(v)
                        if v>1:
                            ya=int(v) if v>1 else int(v*100)
                        else:
                            ya=int(v*100)
                        if 0 < ya < 100:
                            break
                    except:
                        continue
            if not ya:
                no_price+=1
                ya=50  # temp for counting
            
            entry={"over":ya,"under":100-ya,"vol":m.get("volume",0) or 0,"title":title,"tl":tl,"exp":m.get("expiration_time","")[:16],"has_price": m.get("yes_ask") is not None}
            
            # Real vs Parlay - V110 shows first 1000 all parlay
            is_parlay = title.lower().count("yes")>=2 or title.count(",")>=2 or title.count(",yes")>=1
            if is_parlay:
                parlay.append(entry)
            else:
                real.append(entry)

        # Group for middle
        def group_mid(arr):
            g={}
            for s in arr:
                key=s["title"][:40]
                if key not in g:
                    g[key]={"o25":[],"o35":[],"title":s["title"]}
                if "2.5" in s["tl"]:
                    g[key]["o25"].append(s)
                elif "3.5" in s["tl"]:
                    g[key]["o35"].append(s)
            middles=0
            for v in g.values():
                if v["o25"] and v["o35"]:
                    middles+=1
            return len(g), middles

        real_games, real_mid = group_mid(real)
        par_games, par_mid = group_mid(parlay)

        if not hasattr(analyze,"first"):
            analyze.first=True
            msg=f"V112 BOTH - Deploy OK!\n"
            msg+=f"Scanned {len(ms)} -> Total Soccer {len(all_soccer)} (V103 had 94 in 1000)\n"
            msg+=f"Real Single {len(real)} Games {real_games} Middles {real_mid}\n"
            msg+=f"Parlay {len(parlay)} Games {par_games} Middles {par_mid}\n"
            msg+=f"No Price: {no_price} (markets endpoint yes_ask=None)\n\n"
            msg+=f"Sample Real:\n"
            for r in real[:2]:
                msg+=f"{r['title'][:50]}\n"
            msg+=f"\nSample Parlay:\n"
            for p in parlay[:2]:
                msg+=f"{p['title'][:50]}\n"
            msg+=f"\nBoth saved!"
            send(msg)

        if real_mid==0 and par_mid==0 and len(all_soccer)>0:
            if not hasattr(analyze,"last_no") or time.time()-analyze.last_no > 3600:
                analyze.last_no=time.time()
                send(f"No middle yet - Scanned {len(ms)} -> Real {len(real)} Parlay {len(parlay)} Total {len(all_soccer)} - V103 clone, checking 5min")

    except Exception as e:
        send(f"V112 Error {str(e)[:200]}")

def bot_loop():
    time.sleep(3)
    send(f"V112 BOTH starting - V103 clone + 5000 scan + Price fix - Deploy OK!")
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
        self.wfile.write(b"V112 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
