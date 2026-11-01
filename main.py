import os, time, requests, threading, json
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        r=requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=20)
    except: pass

def get_all():
    all_m=[]; cur=None
    for i in range(20):
        try:
            p={"status":"open","limit":500}
            if cur: p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=25)
            if r.status_code!=200: continue
            data=r.json(); ms=data.get("markets",[]); all_m.extend(ms)
            cur=data.get("cursor")
            if not cur: break
            time.sleep(0.5)
        except: break
    return all_m

def analyze():
    print(f"\n=== V30 ===")
    markets=get_all()
    print(f"Total {len(markets)}")
    soccer=[]
    vancouver_raw=[]
    for m in markets:
        title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")+" "+(m.get("no_sub_title","") or "")
        tl=title.lower()
        # Vancouver Seattle MLS
        if "vancouver" in tl or "seattle" in tl or "atlanta" in tl or "nashville" in tl:
            vancouver_raw.append(m)
            if len(vancouver_raw)<=3:
                print(f"VAN SAMPLE RAW: {json.dumps(m, indent=2)[:2000]}")
        # Point Total search - broader: title has Over AND any of goal/total/point OR market has point_total
        if "over" in tl or "point total" in tl or "total" in tl:
            # Also need soccer team
            if any(x in tl for x in ["【entity-vancouver¦canonical_name=Vancouver Whitecaps FC】","【entity-seattle¦canonical_name=Seattle Sounders FC】","atlanta","nashville","mls","soccer","premier","【entity-milan¦canonical_name=AC Milan】","inter","【entity-liverpool¦canonical_name=Liverpool】","【entity-arsenal¦canonical_name=Arsenal】","lafc"]):
                ya=None
                for k in ["yes_ask","yes_bid","last_price","price","yes_price","close_price"]:
                    v=m.get(k)
                    if v is not None:
                        try: ya=int(float(v)); break
                        except: continue
                if ya is None: ya=43 # fallback for debug
                if 1<=ya<=99:
                    soccer.append({"over":ya,"title":m.get("title",""),"subtitle":m.get("subtitle",""),"yes_sub":m.get("yes_sub_title",""),"ticker":m.get("ticker",""),"vol":m.get("volume",0),"raw":m})

    print(f"Soccer {len(soccer)} 【entity-Vancouver¦canonical_name=Vancouver Whitecaps FC】 raw {len(vancouver_raw)}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V30 FINAL DEBUG - 【entity-Vancouver¦canonical_name=Vancouver Whitecaps FC】 raw JSON log - Over+Goal broad search")

    if vancouver_raw:
        # Send first 【entity-Vancouver¦canonical_name=Vancouver Whitecaps FC】 raw
        first=vancouver_raw[0]
        raw_str=f"Title: {first.get('title')}\nSubtitle: {first.get('subtitle')}\nYes_sub: {first.get('yes_sub_title')}\nTicker: {first.get('ticker')}\nEvent: {first.get('event_ticker')}\nYes_bid: {first.get('yes_bid')} Yes_ask: {first.get('yes_ask')} Last: {first.get('last_price')}\nVolume: {first.get('volume')}"
        send(f"🔍 VANCOUVER RAW FOUND {len(vancouver_raw)} markets:\n{raw_str[:1000]}\n\nSoccer filtered {len(soccer)}")

    if soccer:
        msg=f"🔥 PRE-MATCH MIDDLE - {len(soccer)} Point Total (ပွဲပြီးတာ မပါ)\n\n"
        for i,s in enumerate(soccer[:5],1):
            msg+=f"{i}. {s['title'][:40]} | {s['subtitle'][:30]}\n   Over {s['over']}c Vol {s['vol']} {s['ticker'][:20]}\n   Middle: Over 2.5 + Under 3.5 = 3 ဂိုးဆို 2 ဖက်နိုင်!\n\n"
        send(msg)
    else:
        if vancouver_raw:
            send(f"Status - Total {len(markets)}, Vancouver {len(vancouver_raw)} တွေ့တယ်, Soccer filter {len(soccer)} - Raw ထုတ်ပြီးပြီ - Title ထဲ Over မပါလို့")
        else:
            send(f"Status - Total {len(markets)}, Vancouver 0 - Kalshi MLS market ပုံစံပြောင်းသွားပြီ - Full raw စစ်မယ်")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(180)
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V30 running")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
