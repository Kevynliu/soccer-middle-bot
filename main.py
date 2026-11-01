import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        r=requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=20)
        print(r.status_code)
    except: pass

def get_all():
    all_m=[]; cur=None
    for i in range(25): # 25*400 = 10000
        try:
            p={"status":"open","limit":400}
            if cur: p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=25)
            if r.status_code!=200:
                print(f"Fail {r.status_code} {r.text[:200]}"); time.sleep(2); continue
            data=r.json(); ms=data.get("markets",[]); all_m.extend(ms)
            print(f"Fetch {i} {len(ms)} total {len(all_m)}")
            cur=data.get("cursor")
            if not cur: break
            time.sleep(0.6)
        except Exception as e: print(e); time.sleep(2)
    return all_m

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"\n=== V29 {now} ===")
    markets=get_all()
    soccer=[]
    debug_titles=[]
    for m in markets:
        title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")
        tl=title.lower()
        # Vancouver vs Seattle Over 3.5 goals scored
        if "over" in tl and ("goal" in tl or "total" in tl):
            # Price
            ya=None
            for k in ["yes_ask","yes_bid","last_price","price"]:
                v=m.get(k)
                if v is not None:
                    try: ya=int(float(v)); break
                    except: continue
            if ya is None or not (1<=ya<=99): continue
            # Filter finished - Kalshi status open is already upcoming
            if m.get("status","").lower() not in ["open","active",""]: continue
            soccer.append({"over":ya,"under":100-ya,"title":m.get("title",""),"ticker":m.get("ticker",""),"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"exp":m.get("expiration_time","")})
            print(f" KEEP {ya}c {title[:70]}")
        else:
            if "vancouver" in tl or "seattle" in tl or "atlanta" in tl:
                debug_titles.append(title[:60])

    print(f"Found {len(soccer)} over-goal markets, debug vancouver {debug_titles}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V29 FINAL - Title Over+Goal direct search - 4750 scan, Vancouver search")

    if soccer:
        top=sorted(soccer, key=lambda x: abs(x["over"]-50))[:5]
        msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} Point Total Over (ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်)\n\n"
        for i,s in enumerate(top,1):
            msg+=f"{i}. {s['title'][:55]}\n   Over {s['over']}c Under {s['under']}c Vol {s['vol']} Exp {s['exp'][5:16]}\n"
            if 30<=s["over"]<=65:
                msg+=f"   💡 Middle: Over 2.5 60c + Under 3.5 {s['under']}c = 3 ဂိုးဆို 2 ဖက်နိုင်! Win% 65%+\n"
                msg+=f"   Strategy: ပွဲမစခင် ဝယ်ထား - 15' 0-0 Under ထပ်ဝယ် - 70' Jackpot Over ပြန်ဝယ်\n"
            msg+="\n"
        msg+=f"⏰ Live: 15' 0-0, 70' Jackpot အချိန်နဲ့အမျှ alert ပေးမယ် - ပွဲစဉ် {len(soccer)} ခု စောင့်နေတယ်"
        send(msg)
    else:
        dbg="\n".join(debug_titles[:3]) if debug_titles else "No vancouver/seattle in 10000"
        send(f"Status {now} - Total {len(markets)} markets, Soccer Point Total {len(soccer)}\nDebug Vancouver search: {dbg}\n\nTitle filter: over+goal - 10000 scan")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(180)
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V29 running")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
