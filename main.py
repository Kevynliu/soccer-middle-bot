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
            if r.status_code==429:
                time.sleep(5)
                continue
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
        ms=get_markets(total=5000)
        if not ms:
            return
        pst=datetime.utcnow() - timedelta(hours=7)
        
        groups={}
        for m in ms:
            title=m.get("title","")
            tl=(title+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "goals scored" not in tl: continue
            if "over" not in tl: continue
            if "2.5" not in tl and "3.5" not in tl: continue
            
            key=title[:45]
            if key not in groups:
                groups[key]={"o25":[],"o35":[],"title":title}
            
            # V103 logic - try any price field
            ya=None
            for k in ["yes_ask","yes_bid","last_price"]:
                v=m.get(k)
                if v not in [None,"",0]:
                    try:
                        fv=float(v)
                        ya=int(fv) if fv>1 else int(fv*100)
                        if 0 < ya < 100:
                            break
                    except:
                        pass
            if not ya:
                ya=50  # EST if no price
            
            e={"over":ya,"under":100-ya,"title":title}
            if "2.5" in tl:
                groups[key]["o25"].append(e)
            else:
                groups[key]["o35"].append(e)
        
        middles=[]
        for g in groups.values():
            if g["o25"] and g["o35"]:
                a=min(g["o25"], key=lambda x: x["over"])
                b=min(g["o35"], key=lambda x: x["over"])
                cost=a["over"]+b["under"]
                if cost<=130:
                    middles.append({"title":g["title"],"o25":a,"o35":b,"cost":cost,"profit":200-cost})
        
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V116 STABLE - Deploy OK!\nScanned {len(ms)} -> Soccer Groups {len(groups)} Middles {len(middles)}\nV103 clone 5000 scan - No price filter - Both saved\nPST {pst.strftime('%m-%d %H:%M')} - Real vs 0 at night normal, Parlay {len(middles)}")
        
        if middles:
            txt=f"🎯 MIDDLE 🔥 {len(middles)} found - {pst.strftime('%H:%M PST')}\n"
            for i,m in enumerate(middles[:6],1):
                txt+=f"{i}. {m['title'][:48]}\n O2.5 {m['o25']['over']}c + U3.5 {m['o35']['under']}c Cost {m['cost']}c +{m['profit']}c\n\n"
            send(txt)
        else:
            if not hasattr(analyze,"last_no") or time.time()-analyze.last_no > 10800:
                analyze.last_no=time.time()
                send(f"No middle in {len(ms)} -> Groups {len(groups)} - {pst.strftime('%H:%M PST')} checking 5min")

    except Exception as e:
        send(f"V116 Error {e}")

def bot_loop():
    time.sleep(3)
    send(f"V116 STABLE starting - V103 clone 5000 scan - Deploy OK!")
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
        self.wfile.write(b"V116")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
