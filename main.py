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

def get_ob_price(ticker):
    try:
        r=requests.get(f"{BASE}/markets/{ticker}/orderbook", timeout=8)
        if r.status_code!=200:
            return None, f"HTTP {r.status_code}"
        j=r.json()
        ob=j.get("orderbook",{})
        # Try all formats
        for k in ["yes_dollars","yes","yes_bids"]:
            arr=ob.get(k,[])
            if arr and len(arr)>0:
                try:
                    first=arr[0]
                    price_str=str(first[0] if isinstance(first,(list,tuple)) else first)
                    fv=float(price_str)
                    price=int(fv*100) if fv<=1 else int(fv)
                    if 0 < price < 100:
                        return price, f"{k}={price_str}"
                except:
                    pass
        return None, f"no price keys {list(ob.keys())[:3]}"
    except Exception as e:
        return None, str(e)[:60]

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
            if "over 2.5" not in tl and "over 3.5" not in tl: continue
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
            else:
                groups[key]["o35"].append(e)
        
        pairs=[]
        for g in groups.values():
            if g["o25"] and g["o35"]:
                a=max(g["o25"], key=lambda x: x["vol"] or 0)
                b=max(g["o35"], key=lambda x: x["vol"] or 0)
                pairs.append((g["title"],a,b))
        
        if not hasattr(analyze,"first"):
            analyze.first=True
            msg=f"V118 REAL - Deploy OK!\nScanned {len(ms)} -> Groups {len(groups)} Pairs {len(pairs)}\nTesting orderbook for 3 tickers..."
            send(msg)
            
            # DEBUG 3 tickers orderbook
            debug_txt=""
            for i,(title,a,b) in enumerate(pairs[:3]):
                price_a, info_a = get_ob_price(a["ticker"])
                time.sleep(1)
                price_b, info_b = get_ob_price(b["ticker"])
                time.sleep(1)
                debug_txt+=f"{i+1}. {title[:35]}\n O2.5 {a['ticker'][:25]} -> {price_a} ({info_a})\n U3.5 {b['ticker'][:25]} -> {price_b} ({info_b})\n\n"
            
            send(f"V118 Orderbook DEBUG:\n{debug_txt[:1000]}")
            return
        
        # Normal loop - only 3 orderbook calls per cycle
        real_middles=[]
        for title,a,b in pairs[:3]:
            o25=a["over"] or get_ob_price(a["ticker"])[0]
            time.sleep(1)
            o35=b["over"] or get_ob_price(b["ticker"])[0]
            time.sleep(1)
            
            if o25 and o35:
                cost=o25 + (100-o35)
                if 60 <= cost <= 135:
                    real_middles.append({"title":title,"o25":o25,"o35":o35,"cost":cost,"profit":200-cost})
        
        if real_middles:
            txt=f"⚽ LIVE MIDDLE 🔥 {len(real_middles)} - {pst.strftime('%H:%M PST')}\n"
            for i,m in enumerate(real_middles[:4],1):
                txt+=f"{i}. {m['title'][:42]}\n O2.5 {m['o25']}c + U3.5 {100-m['o35']}c Cost {m['cost']}c +{m['profit']}c LIVE\n\n"
            send(txt)
        else:
            if not hasattr(analyze,"last_no") or time.time()-analyze.last_no > 3600:
                analyze.last_no=time.time()
                send(f"No LIVE middle - Pairs {len(pairs)} Groups {len(groups)} - {pst.strftime('%H:%M PST')} - Orderbook 429 or no liquidity, checking 5min")

    except Exception as e:
        send(f"V118 Error {str(e)[:150]}")

def bot_loop():
    time.sleep(3)
    send(f"V118 REAL starting - 5000 scan + Over 2.5/3.5 + Orderbook 3 DEBUG - Deploy OK!")
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
        self.wfile.write(b"V118")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
