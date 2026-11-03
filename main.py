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

def get_ob(ticker):
    try:
        r=requests.get(f"{BASE}/markets/{ticker}/orderbook", timeout=10)
        if r.status_code!=200:
            return None
        ob=r.json().get("orderbook",{})
        for k in ["yes_dollars","yes"]:
            arr=ob.get(k)
            if arr and len(arr)>0:
                v=arr[0]
                price_str=str(v[0] if isinstance(v,(list,tuple)) else v)
                try:
                    fv=float(price_str)
                    return int(fv*100) if fv<=1 else int(fv)
                except:
                    pass
    except:
        pass
    return None

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
            # FIX: Only 2.5 and 3.5, not 0.5/1.5
            if "over 2.5" not in tl and "over 3.5" not in tl:
                continue
            
            key=title[:45]
            if key not in groups:
                groups[key]={"o25":[],"o35":[],"title":title}
            
            ticker=m.get("ticker","")
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
            
            e={"over":ya,"ticker":ticker,"vol":m.get("volume",0) or 0}
            if "over 2.5" in tl:
                groups[key]["o25"].append(e)
            elif "over 3.5" in tl:
                groups[key]["o35"].append(e)
        
        # Find pairs
        pairs=[]
        for g in groups.values():
            if g["o25"] and g["o35"]:
                a=max(g["o25"], key=lambda x: x["vol"] or 0)
                b=max(g["o35"], key=lambda x: x["vol"] or 0)
                pairs.append((g["title"],a,b))
        
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V117 REAL PRICE - Deploy OK!\nScanned {len(ms)} -> Groups {len(groups)} Pairs {len(pairs)}\nFilter Over 2.5/3.5 only (not 0.5/1.5)\nFetching orderbook for top 10...")
        
        real_middles=[]
        for title,a,b in pairs[:10]:
            # Try markets price first, then orderbook
            o25=a["over"]
            o35=b["over"]
            
            if not o25:
                o25=get_ob(a["ticker"])
                time.sleep(0.8)
            if not o35:
                o35=get_ob(b["ticker"])
                time.sleep(0.8)
            
            if o25 and o35 and 0 < o25 < 100 and 0 < o35 < 100:
                cost=o25 + (100-o35)
                if 60 <= cost <= 135:
                    real_middles.append({"title":title,"o25":o25,"o35":o35,"cost":cost,"profit":200-cost})
        
        if real_middles:
            txt=f"⚽ REAL MIDDLE 🔥 {len(real_middles)} LIVE PRICE - {pst.strftime('%H:%M PST')}\n"
            for i,m in enumerate(real_middles[:5],1):
                txt+=f"{i}. {m['title'][:45]}\n O2.5 {m['o25']}c + U3.5 {100-m['o35']}c Cost {m['cost']}c Profit +{m['profit']}c LIVE\n\n"
            send(txt)
        else:
            if pairs:
                # Show why no middle - price missing
                if not hasattr(analyze,"last_no") or time.time()-analyze.last_no > 3600:
                    analyze.last_no=time.time()
                    sample_price=[]
                    for _,a,b in pairs[:3]:
                        sample_price.append(f"O2.5 price {a['over']} ticker {a['ticker'][:20]} O3.5 price {b['over']}")
                    send(f"Found {len(pairs)} pairs but no LIVE price in markets endpoint\nNeed orderbook - {sample_price[0][:80] if sample_price else ''}\nChecking 5min - {pst.strftime('%H:%M PST')}")

    except Exception as e:
        send(f"V117 Error {str(e)[:200]}")

def bot_loop():
    time.sleep(3)
    send(f"V117 REAL PRICE starting - Over 2.5/3.5 only + Orderbook LIVE - Deploy OK!")
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
        self.wfile.write(b"V117")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
