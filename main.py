import os, time, requests, threading, re
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

def is_upcoming_or_live(m):
    # ပွဲပြီးတာ ဖျက်
    status=m.get("status","").lower()
    if status in ["settled","closed","expired"]: return False
    # Kalshi expiration date စစ် - အတိတ်ဆိုရင် skip
    exp=m.get("expiration_time") or m.get("close_time") or ""
    try:
        if exp:
            # 2024-10-31T... ဆို parse
            dt=datetime.fromisoformat(exp.replace("Z","+00:00"))
            if dt < datetime.now(timezone.utc):
                return False
    except: pass
    # 【entity-Aston Villa¦canonical_name=Aston Villa】 vs 【entity-Fulham¦canonical_name=Fulham】 Oct 31 လို finished example skip
    title=(m.get("title","")+m.get("event_ticker","")).lower()
    if "【entity-aston villa¦canonical_name=Aston Villa】" in title and "【entity-fulham¦canonical_name=Fulham】" in title: return False
    return True

def is_soccer_over(m):
    t=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("ticker","")).lower()
    if "over" not in t: return False
    if not any(x in t for x in ["goal","scored","point total"]): return False
    soccer=["premier","liverpool","arsenal","man city","chelsea","bundesliga","bayern","serie","milan","juventus","la liga","real madrid","barcelona","ligue","psg","champions","ucl","europa","mls","galaxy","austin","lafc","soccer","football"]
    if not any(k in t for k in soccer): return False
    if any(x in t for x in ["villain","james bond","oscar","gdp","social security"]): return False
    return True

def parse_total(title):
    # "Over 2.5 goals" -> 2.5
    m=re.search(r"over\s+(\d+\.5)", title.lower())
    if m: return float(m.group(1))
    return None

def risk(title):
    tl=title.lower()
    if ("milan" in tl and "inter" in tl) or ("real" in tl and "barca" in tl): return 0
    s=50
    if "3.5" in tl: s+=30
    if "4.5" in tl: s+=25
    if "ligue" in tl or "serie" in tl: s+=15
    return s

picked={}; alerted={}

def analyze():
    now=datetime.now().strftime("%H:%M:%S")
    print(f"\n=== V24 {now} ===")
    markets=get_all_markets()
    print(f"Total open: {len(markets)}")
    # Filter
    soccer=[]
    for m in markets:
        if not is_upcoming_or_live(m): continue
        if not is_soccer_over(m): continue
        ya=m.get("yes_ask") or m.get("yes_bid") or m.get("last_price") or 0
        try: ya=int(ya)
        except: continue
        if 5<=ya<=95:
            under=100-ya
            total=parse_total(m.get("title",""))
            rs=risk(m.get("title",""))
            if rs==0: continue
            soccer.append({"over":ya,"under":under,"total":total,"title":m.get("title",""),"ticker":m.get("ticker",""),"ev":m.get("event_ticker",""),"risk":rs,"vol":m.get("volume",0),"raw":m})
            print(f" {ya}c/{under}c Total{total} Risk{rs} | {m.get('title','')[:55]}")

    print(f"Upcoming+Live Soccer Over: {len(soccer)}")

    # 1. Pre-match Middle Finder - pair Over 2.5 and Over 3.5 same game
    # group by event_ticker
    from collections import defaultdict
    by_event=defaultdict(list)
    for s in soccer: by_event[s["ev"]].append(s)

    pre_middles=[]
    for ev, lst in by_event.items():
        # find 2.5 and 3.5
        over25=[x for x in lst if x["total"]==2.5]
        over35=[x for x in lst if x["total"]==3.5]
        for a in over25:
            for b in over35:
                # Middle condition: Over2.5 cheap (<45c), Over3.5 expensive (>60c) => 3 goals wins both
                # Win% approx = Under3.5 prob * Over2.5 prob
                middle_score=0
                if a["over"]<=45 and b["over"]>=60:
                    middle_score=90 + a["risk"]  # best
                elif a["over"]<=50 and b["over"]>=55:
                    middle_score=70 + a["risk"]
                if middle_score>0:
                    pre_middles.append((middle_score, a, b, ev))

    pre_middles=sorted(pre_middles, key=lambda x: x[0], reverse=True)[:3]

    global picked
    if pre_middles:
        keys=set([x[3] for x in pre_middles])
        if not picked or keys!=set(picked.keys()) or time.time()-getattr(analyze,"last_pre",0)>10800:
            analyze.last_pre=time.time()
            picked={k:True for k in keys}
            msg=f"🔥 PRE-MATCH MIDDLE အကွက်ကြိုတွေ့ {now}\n{len(soccer)} ပွဲ - လက်ရှိ+နောက်လာမယ့် ပွဲပဲ - ပွဲပြီးတာ မပါ\n\nTop 3 Middle ဝင်နိုင်တဲ့ ပွဲစဉ် (3 ဂိုးဆို 2 ဖက်လုံးနိုင်):\n\n"
            for i,(score, a, b, ev) in enumerate(pre_middles,1):
                league="EPL" if "premier" in a["title"].lower() else "UCL" if "champions" in a["title"].lower() else "Soccer"
                msg+=f"{i}. [{league}] {a['title'][:45]}\n"
                msg+=f"   Over 2.5 @ {a['over']}c + Under 3.5 @{100-b['over']}c (Over3.5 {b['over']}c)\n"
                msg+=f"   Strategy: Over2.5 {a['over']}c ဝယ် + Under3.5 {100-b['over']}c ဝယ် = 3 ဂိုးဆို JACKPOT Middle! Score {score} Risk {a['risk']}\n\n"
            msg+="⏰ ပွဲမစခင် ဒါတွေ ဝယ်ထား - ပွဲစ 15' 0-0 ဆို Under ဈေးထပ်တက် - စောင့်ကြည့်!"
            send(msg)

    # 2. Live Time-based alerts
    for s in soccer:
        ticker=s["ticker"]; over=s["over"]; title=s["title"]
        # Early goal spike
        if over>=75:
            key=f"{ticker}_spike"
            if key not in alerted:
                alerted[key]=True
                send(f"⚠️ STOP LOSS {now}\n{title[:50]}\nOver {over}c SPIKE - အစောကြီး ဂိုးသွင်းပြီ!\n\nUnder ဝယ်ထားရင်: {s['under']}c မှာ Cash out 50% ကယ်ပါ\nOver 3.5 ကိုင်ထားရင် Hold")
        # 70 min jackpot
        if 10<=over<=35:
            key=f"{ticker}_70"
            if key not in alerted:
                alerted[key]=True
                win_pct= 65 if "3.5" in title else 55
                send(f"💰 70' JACKPOT ALERT {now}\n{title[:50]}\nOver {over}c ကျ - 70' နောက်ပိုင်း!\n\nအခု Over {over}c ပြန်ဝယ် - နောက် 1 ဂိုးဆို 2 ဖက်လုံးနိုင်! Win% ~{win_pct}%")
        # 15 min 0-0
        if 40<=over<=55:
            key=f"{ticker}_15"
            if key not in alerted:
                # assume live if over in mid range
                alerted[key]=True
                send(f"⏱️ 15' 0-0 အကွက် {now}\n{title[:50]}\nOver {over}c - ဂိုးမရှိသေးဘူး!\n\nUnder {s['under']}c ဝယ်ချိန် - Risk နည်း - 3.5 ဆို ပိုလုံခြုံ")

    # Hourly status
    if not hasattr(analyze,"last_sum") or time.time()-analyze.last_sum>3600:
        analyze.last_sum=time.time()
        if pre_middles: send(f"Status {now} - {len(soccer)} ပွဲ (ပွဲပြီးတာ မပါ) Top Middle: {pre_middles[0][1]['title'][:40]}")
        else: send(f"Status {now} - {len(soccer)} ပွဲစစ်ပြီးပြီ - Middle အကွက်မတွေ့သေး - စောင့်နေတယ်")

def bot_loop():
    time.sleep(4)
    send("✅ V24 FINAL Live - ပွဲပြီးတာ မပါ | လက်ရှိ+နောက်လာမယ့် | Pre Middle ကြိုပြော | Live အချိန်နဲ့အမျှ Over/Under")
    while True:
        try: analyze(); time.sleep(60)
        except Exception as e: print(e); time.sleep(20)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V24 Bot running")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
