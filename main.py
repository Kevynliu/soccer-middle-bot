import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"
print(f"DEBUG BOT len={len(BOT)} CHAT={CHAT}")

def send(msg):
    try:
        r=requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=15)
        print(f"TG {r.status_code}")
    except Exception as e: print(f"TG err {e}")

def get_all_markets():
    all_m=[]; cur=None
    for _ in range(8):
        try:
            p={"status":"open","limit":500}
            if cur: p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code!=200: break
            data=r.json(); ms=data.get("markets",[]); all_m.extend(ms)
            cur=data.get("cursor")
            if not cur or len(ms)<500: break
            time.sleep(0.4)
        except: break
    return all_m

def is_upcoming(m):
    if m.get("status","").lower() in ["settled","closed","expired"]: return False
    exp=m.get("expiration_time") or m.get("close_time") or ""
    try:
        if exp:
            dt=datetime.fromisoformat(exp.replace("Z","+00:00"))
            if dt < datetime.now(timezone.utc): return False
    except: pass
    return True

def is_soccer(m):
    # ပိုကျယ်အောင် - over မပါလဲ goal ပါရင် ယူ
    t=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("ticker","")+" "+m.get("event_ticker","")).lower()
    if not any(x in t for x in ["goal","point total","soccer","premier","bundesliga","la liga","serie","ligue 1","ucl","champions league","mls"]): 
        return False
    if any(x in t for x in ["villain","james bond","oscar","gdp","social security","city champs"]): return False
    return True

picked={}; alerted={}

def analyze():
    now=datetime.now().strftime("%H:%M:%S")
    print(f"\n=== V25 {now} ===")
    markets=get_all_markets()
    print(f"Total open: {len(markets)}")
    soccer=[]
    for m in markets:
        if not is_upcoming(m): continue
        if not is_soccer(m): continue
        ya=m.get("yes_ask") or m.get("yes_bid") or m.get("last_price") or 0
        try: ya=int(ya)
        except: continue
        if 5<=ya<=95:
            # Debug sample
            if len(soccer)<5:
                print(f" Sample: {ya}c | {m.get('title','')[:70]} | {m.get('ticker','')}")
            soccer.append({"over":ya,"under":100-ya,"title":m.get("title",""),"ticker":m.get("ticker",""),"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"raw":m})

    print(f"Upcoming+Live Soccer: {len(soccer)}")
    
    # Pre-match middle - Over 2.5 cheap
    top=[]
    for s in soccer:
        # middle potential: Over price 35-55c (balanced) + high volume + upcoming
        score=0
        if 35<=s["over"]<=55: score+=50
        if 30<=s["over"]<=60: score+=30
        if "3.5" in s["title"]: score+=30
        if "premier" in s["title"].lower(): score+=10
        if score>0: top.append((score,s))
    
    top=sorted(top, key=lambda x: x[0], reverse=True)[:3]

    global picked
    if top:
        keys=set([x[1]["ticker"] for x in top])
        if not picked or keys!=set(picked.keys()) or time.time()-getattr(analyze,"last_pre",0)>10800:
            analyze.last_pre=time.time()
            picked={k:True for k in keys}
            msg=f"🔥 PRE-MATCH MIDDLE အကွက် {now}\n{len(soccer)} ပွဲ (ပွဲပြီးတာ မပါ) - လက်ရှိ+နောက်လာမယ့်\n\nTop 3 ဂိုးပေါင်း Middle ဝင်နိုင်တဲ့ပွဲ:\n\n"
            for i,(score,s) in enumerate(top,1):
                msg+=f"{i}. {s['title'][:50]}\n   Over {s['over']}c Under {s['under']}c Vol {s['vol']} Score {score}\n"
                if "3.5" in s["title"]:
                    msg+=f"   SAFER: 4 ဂိုးမှ ရှုံး - Under 3.5 လုံခြုံ\n"
                msg+=f"   Strategy: ပွဲမစခင် Under {s['under']}c ဝယ်, 15' 0-0 ဆို ထပ်ဝယ်\n\n"
            send(msg)

    # Hourly status only - no more 1 min spam
    if not hasattr(analyze,"last_sum") or time.time()-analyze.last_sum>3600:
        analyze.last_sum=time.time()
        if top:
            send(f"Status {now} - {len(soccer)} ပွဲ (ပွဲပြီးတာ မပါ), Top: {top[0][1]['title'][:40]} Over {top[0][1]['over']}c")
        else:
            # ဘာမှ မတွေ့ရင် sample 3 ခု ပြမယ် debug အတွက်
            if soccer:
                sample="\n".join([f"- {s['title'][:50]} {s['over']}c" for s in soccer[:3]])
                send(f"Status {now} - {len(soccer)} soccer markets တွေ့တယ်, Middle filter နဲ့ မကိုက်သေး:\n{sample}\n\nFilter ကို လျှော့ပေးမယ် - စောင့်နေတယ်")
            else:
                send(f"Status {now} - {len(markets)} total markets, soccer 0 - Kalshi မှာ ဒီချိန် soccer Over ပိတ်ထားတယ် - နောက် 1 နာရီနေရင် ပြန်စစ်မယ်")

def bot_loop():
    time.sleep(3)
    send("✅ V25 FINAL Live - Spam fix + Middle finder - ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်, Pre Middle ကြိုပြော, Live အချိန်နဲ့အမျှ")
    while True:
        try: analyze(); time.sleep(300)  # 5 မိနစ်တစ်ခါ စစ် - 1 မိနစ် spam မဟုတ်တော့
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V25 Bot running")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
