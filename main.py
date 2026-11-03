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
            if r.status_code==429:
                time.sleep(5)
                continue
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
        
        soccer=[]
        parlay_groups={}
        real_groups={}
        
        for m in ms:
            title=m.get("title","")
            tl=(title+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "goals scored" not in tl: continue
            if "over" not in tl: continue
            if "2.5" not in tl and "3.5" not in tl: continue
            if "tampa bay" in tl or "edmonton" in tl or "ottawa" in tl: continue
            
            soccer.append(m)
            # price
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
                continue
            
            is_real = (" vs " in title.lower()) and title.lower().count("yes")<=1
            
            key=title[:50]
            target=real_groups if is_real else parlay_groups
            
            if key not in target:
                target[key]={"o25":[],"o35":[],"title":title}
            
            entry={"over":ya,"under":100-ya,"title":title}
            if "2.5" in tl:
                target[key]["o25"].append(entry)
            elif "3.5" in tl:
                target[key]["o35"].append(entry)
        
        real_middles=[]
        for g in real_groups.values():
            if g["o25"] and g["o35"]:
                a=min(g["o25"], key=lambda x: x["over"])
                b=min(g["o35"], key=lambda x: x["over"])
                cost=a["over"]+b["under"]
                if cost<=130:
                    real_middles.append({"title":g["title"],"o25":a,"o35":b,"cost":cost,"profit":200-cost})
        
        parlay_middles=[]
        for g in parlay_groups.values():
            if g["o25"] and g["o35"]:
                a=min(g["o25"], key=lambda x: x["over"])
                b=min(g["o35"], key=lambda x: x["over"])
                cost=a["over"]+b["under"]
                if cost<=130:
                    parlay_middles.append({"title":g["title"],"o25":a,"o35":b,"cost":cost,"profit":200-cost})
        
        if not hasattr(analyze,"first"):
            analyze.first=True
            msg=f"V114 PRODUCTION - Deploy OK!\n"
            msg+=f"Scanned {len(ms)} -> Soccer {len(soccer)}\n"
            msg+=f"Real Single {len(real_groups)} Middles {len(real_middles)} (vs markets - morning only)\n"
            msg+=f"Parlay {len(parlay_groups)} Middles {len(parlay_middles)}\n"
            msg+=f"PST Now {pst_now.strftime('%m-%d %H:%M')} - Real 0 at night = normal, will appear 6-8 AM PST\n"
            msg+=f"Both saved - Parlay trading at night!"
            send(msg)
        
        if real_middles:
            txt=f"⚽ REAL SINGLE MIDDLE 🔥 {len(real_middles)} found - {pst_now.strftime('%m-%d %H:%M PST')}\n"
            for i,m in enumerate(real_middles[:4],1):
                txt+=f"{i}. {m['title'][:45]}\n O2.5 {m['o25']['over']}c + U3.5 {m['o35']['under']}c Cost {m['cost']}c Profit +{m['profit']}c\n\n"
            send(txt)
        
        if parlay_middles:
            txt=f"🎯 PARLAY MIDDLE 🔥 {len(parlay_middles)} found\n"
            for i,m in enumerate(parlay_middles[:5],1):
                txt+=f"{i}. {m['title'][:50]}\n O2.5 {m['o25']['over']}c + U3.5 {m['o35']['under']}c Cost {m['cost']}c +{m['profit']}c\n\n"
            send(txt)
        
        if not real_middles and not parlay_middles:
            if not hasattr(analyze,"last_no") or time.time()-analyze.last_no > 10800:
                analyze.last_no=time.time()
                send(f"No middle in {len(ms)} -> Real {len(real_groups)} Parlay {len(parlay_groups)} - Night time Real 0 normal, Parlay {len(parlay_groups)} checking 5min - {pst_now.strftime('%H:%M PST')}")

    except Exception as e:
        send(f"V114 Error {str(e)[:150]}")

def bot_loop():
    time.sleep(3)
    send(f"V114 PRODUCTION starting - 12000 scan + Real Morning + Parlay Night + Both Saved - Deploy OK!")
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
        self.wfile.write(b"V114 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
