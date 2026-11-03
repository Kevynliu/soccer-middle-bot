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
            time.sleep(0.5)
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
        total_goals=0
        with_vol=0
        cross=0
        
        for m in ms:
            title=m.get("title","")
            tl=(title+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "goals scored" not in tl: continue
            total_goals+=1
            
            if "crosscategory" in m.get("ticker","").lower():
                cross+=1
            
            vol=m.get("volume",0) or 0
            if vol>0:
                with_vol+=1
            
            if "over 2.5" not in tl and "over 3.5" not in tl: continue
            
            key=title[:45]
            if key not in groups:
                groups[key]={"o25":[],"o35":[],"title":title}
            
            ya=None
            source="None"
            for k in ["yes_ask","yes_bid","last_price"]:
                v=m.get(k)
                if v not in [None,"",0]:
                    try:
                        fv=float(v)
                        ya=int(fv) if fv>1 else int(fv*100)
                        if 0 < ya < 100:
                            source=k
                            break
                    except:
                        pass
            
            e={"over":ya,"vol":vol,"source":source,"ticker":m.get("ticker","")[:30]}
            if "over 2.5" in tl:
                groups[key]["o25"].append(e)
            else:
                groups[key]["o35"].append(e)
        
        pairs=[]
        valid_pairs=[]
        for g in groups.values():
            if g["o25"] and g["o35"]:
                pairs.append(g)
                # Check if has real price and volume
                has_price = any(x["over"] for x in g["o25"]+g["o35"])
                has_vol = sum(x["vol"] for x in g["o25"]+g["o35"]) > 0
                if has_price and has_vol:
                    valid_pairs.append(g)
        
        if not hasattr(analyze,"first"):
            analyze.first=True
            msg=f"V119 REALITY - Deploy OK!\n"
            msg+=f"Scanned {len(ms)} -> goals scored {total_goals}\n"
            msg+=f"CrossCategory {cross} With Volume {with_vol}\n"
            msg+=f"Over 2.5/3.5 Groups {len(groups)} Pairs {len(pairs)} Valid {len(valid_pairs)}\n"
            msg+=f"PST {pst.strftime('%m-%d %H:%M')} - Night liquidity 0\n\n"
            if pairs:
                msg+=f"Sample pairs (no liquidity at night):\n"
                for g in pairs[:2]:
                    o25=g["o25"][0]
                    o35=g["o35"][0]
                    msg+=f"{g['title'][:40]}\n O2.5 {o25['over']} {o25['source']} vol {o25['vol']} | O3.5 {o35['over']} {o35['source']} vol {o35['vol']}\n\n"
            msg+=f"Real Single vs games morning 6-8 AM PST only!"
            send(msg)
            return
        
        if valid_pairs:
            txt=f"⚽ LIVE MIDDLE 🔥 {len(valid_pairs)} - {pst.strftime('%H:%M PST')}\n"
            for g in valid_pairs[:4]:
                a=max(g["o25"], key=lambda x: x["vol"] or 0)
                b=max(g["o35"], key=lambda x: x["vol"] or 0)
                cost=a["over"]+(100-b["over"]) if a["over"] and b["over"] else 100
                txt+=f"{g['title'][:42]}\n O2.5 {a['over']}c ({a['source']}) + U3.5 {100-b['over'] if b['over'] else 50}c Cost {cost}c vol {a['vol']+b['vol']}\n\n"
            send(txt)
        else:
            if not hasattr(analyze,"last_no") or time.time()-analyze.last_no > 3600:
                analyze.last_no=time.time()
                send(f"No liquid middle - {len(ms)} scan -> {total_goals} goals scored, {cross} cross-category, {with_vol} with volume, {len(pairs)} pairs but 0 liquid - Night 11 PM PST = 0 liquidity normal - Real vs games 6-8 AM PST - {pst.strftime('%H:%M')}")

    except Exception as e:
        send(f"V119 Error {str(e)[:150]}")

def bot_loop():
    time.sleep(3)
    send(f"V119 REALITY starting - 5000 scan + Volume + Liquidity check - Deploy OK!")
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
        self.wfile.write(b"V119")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
