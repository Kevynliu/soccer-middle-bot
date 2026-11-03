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

def get_markets(total=12000):
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
        except:
            break
    return all_ms

def analyze():
    try:
        ms=get_markets(total=12000)
        if not ms:
            return
        utc_now=datetime.utcnow()
        pst_now=utc_now - timedelta(hours=7)
        tomorrow_pst=pst_now + timedelta(days=1)
        
        all_soccer=[]
        real=[]
        parlay=[]
        vs_count=0
        no_vs=[]
        
        for m in ms:
            title=m.get("title","")
            tl=(title+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "goals scored" not in tl: continue
            if "over" not in tl: continue
            if "2.5" not in tl and "3.5" not in tl and "1.5" not in tl: continue
            
            all_soccer.append(m)
            
            # Real = must have vs AND not many yes
            has_vs = " vs " in title.lower() or " vs. " in title.lower() or " v " in title.lower()
            yes_count = title.lower().count("yes ")
            
            if has_vs:
                vs_count+=1
            
            # Price
            ya=50
            has_real_price=False
            for k in ["yes_ask","yes_bid"]:
                v=m.get(k)
                if v not in [None,"",0]:
                    try:
                        fv=float(v)
                        if fv>1:
                            ya=int(fv)
                        else:
                            ya=int(fv*100)
                        if 0 < ya < 100:
                            has_real_price=True
                            break
                    except:
                        pass
            
            entry={"over":ya,"title":title,"tl":tl,"has_vs":has_vs,"yes_count":yes_count,"has_price":has_real_price,"exp":m.get("expiration_time","")[:16]}
            
            if has_vs and yes_count<=1:
                real.append(entry)
            elif yes_count>=2 or title.count(",")>=2:
                parlay.append(entry)
            else:
                no_vs.append(entry)

        def count_middles(arr):
            g={}
            for s in arr:
                key=s["title"][:45]
                if key not in g:
                    g[key]={"o25":[],"o35":[]}
                if "2.5" in s["tl"]:
                    g[key]["o25"].append(s)
                elif "3.5" in s["tl"]:
                    g[key]["o35"].append(s)
            mid=0
            for v in g.values():
                if v["o25"] and v["o35"]:
                    mid+=1
            return len(g), mid

        real_g, real_mid = count_middles(real)
        par_g, par_mid = count_middles(parlay)
        other_g, other_mid = count_middles(no_vs)

        if not hasattr(analyze,"first"):
            analyze.first=True
            msg=f"V113 DEEP 12k - Deploy OK!\n"
            msg+=f"Scanned {len(ms)} -> Total Soccer {len(all_soccer)}\n"
            msg+=f"Real (vs + yes<=1) {len(real)} Games {real_g} Middles {real_mid}\n"
            msg+=f"Parlay {len(parlay)} Games {par_g} Middles {par_mid}\n"
            msg+=f"Other (no vs, no parlay) {len(no_vs)} Games {other_g}\n"
            msg+=f"Has 'vs' in title: {vs_count}\n\n"
            msg+=f"Sample Real vs:\n"
            for r in real[:3]:
                msg+=f"{r['title'][:55]}\n"
            msg+=f"\nSample Other:\n"
            for r in no_vs[:3]:
                msg+=f"{r['title'][:55]}\n"
            msg+=f"\nTomorrow {tomorrow_pst.strftime('%m-%d')} PST - Real 0 = markets not listed yet (12-24h before game)"
            send(msg)

    except Exception as e:
        send(f"V113 Error {str(e)[:200]}")

def bot_loop():
    time.sleep(3)
    send(f"V113 DEEP starting - 12000 scan + vs filter + Tomorrow check - Deploy OK!")
    while True:
        try:
            analyze()
            time.sleep(600)
        except:
            time.sleep(600)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V113 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
