import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(m):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":m[:3500]}, timeout=10)
    except:
        pass

def get_markets(total=5000):
    all_m=[]
    cur=None
    for _ in range(5):
        try:
            p={"status":"open","limit":1000}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code==429:
                time.sleep(6)
                continue
            d=r.json()
            b=d.get("markets",[])
            if not b:
                break
            all_m.extend(b)
            cur=d.get("cursor")
            if not cur or len(all_m)>=total:
                break
            time.sleep(0.6)
        except:
            break
    return all_m

def price(m):
    for k in ["yes_ask","yes_bid","last_price"]:
        v=m.get(k)
        if v not in [None,"",0]:
            try:
                fv=float(v)
                c=int(fv) if fv>1 else int(fv*100)
                if 0 < c < 100:
                    return c,k
            except:
                pass
    return None,"None"

def analyze():
    try:
        ms=get_markets(5000)
        if not ms:
            return
        pst=datetime.utcnow()-timedelta(hours=7)
        now=datetime.utcnow()
        
        groups={}
        tot=0
        cross=0
        expired=0
        
        for m in ms:
            # expired filter
            exp=m.get("close_time") or m.get("expiration_time") or ""
            try:
                if exp:
                    exp_dt=datetime.fromisoformat(exp.replace("Z","+00:00"))
                    if exp_dt.replace(tzinfo=None) < now - timedelta(hours=1):
                        expired+=1
                        continue
            except:
                pass
            
            t=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "goals scored" not in t:
                continue
            tot+=1
            if "crosscategory" in m.get("ticker","").lower():
                cross+=1
            
            # skip hockey garbage
            if any(x in t for x in ["anaheim","carolina","tampa","edmonton","ottawa","both teams to score"]):
                continue
            
            # soccer only: must have over 2.5 or 3.5
            if "over 2.5" not in t and "over 3.5" not in t:
                continue
            
            key=m.get("title","")[:50]
            if key not in groups:
                groups[key]={"o25":[],"o35":[],"title":m.get("title","")}
            
            c,src=price(m)
            vol=m.get("volume",0) or 0
            e={"c":c,"src":src,"vol":vol,"tk":m.get("ticker","")[:32]}
            if "over 2.5" in t:
                groups[key]["o25"].append(e)
            else:
                groups[key]["o35"].append(e)
        
        pairs=[]
        for g in groups.values():
            if g["o25"] and g["o35"]:
                a=max(g["o25"], key=lambda x: (x["c"] is not None, x["vol"] or 0))
                b=max(g["o35"], key=lambda x: (x["c"] is not None, x["vol"] or 0))
                if a["c"] and b["c"]:
                    cost=a["c"]+(100-b["c"])
                    if cost<=125:
                        pairs.append((g,cost,a,b))
        
        pairs.sort(key=lambda x: x[1])
        
        if not hasattr(analyze,"first"):
            analyze.first=True
            msg=f"V120 FINAL - Deploy OK!\n"
            msg+=f"Scanned {len(ms)} -> {tot} goals Exp {expired} Cross {cross}\n"
            msg+=f"Groups {len(groups)} Pairs {len(pairs)} PST {pst.strftime('%m-%d %H:%M')}\n\n"
            if pairs:
                msg+=f"LIVE Middle {len(pairs)}:\n"
                for g,cost,a,b in pairs[:3]:
                    msg+=f"{g['title'][:42]}\n O2.5 {a['c']}c {a['src']} | O3.5 {b['c']}c Cost {cost}c vol {a['vol']+b['vol']}\n\n"
            else:
                msg+=f"No liquid middle now:\n"
                msg+=f"Today games finished = expired {expired}\n"
                msg+=f"Tomorrow Real vs games not listed yet\n"
                msg+=f"Kalshi lists Real Single 12-24h before game\n"
                msg+=f"Check morning 6-8 AM PST!"
            send(msg)
            return
        
        if pairs:
            txt=f"⚽ MIDDLE LIVE {len(pairs)} - {pst.strftime('%H:%M PST')}\n"
            for g,cost,a,b in pairs[:4]:
                txt+=f"{g['title'][:40]}\n O2.5 {a['c']}c + U3.5 {100-b['c']}c Cost {cost}c vol {a['vol']+b['vol']}\n\n"
            txt+=f"Auto scan 5min"
            send(txt)
        else:
            if not hasattr(analyze,"ln") or time.time()-analyze.ln>3600:
                analyze.ln=time.time()
                send(f"No middle - {len(ms)} scan {tot} goals {len(groups)} groups {len(pairs)} middle - Today expired {expired} - Tomorrow Real vs not listed yet - 6-8 AM PST check - {pst.strftime('%H:%M')}")

    except Exception as e:
        send(f"V120 Err {str(e)[:180]}")

def loop():
    time.sleep(3)
    send(f"V120 FINAL starting - 5000 scan + Expired filter + Real vs focus - Deploy OK!")
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
        self.wfile.write(b"V120")
    def log_message(self,*a):
        pass

threading.Thread(target=loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
