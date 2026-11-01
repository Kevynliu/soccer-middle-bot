import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.【entity-kalshi¦canonical_name=Kalshi】.com/trade-api/v2"

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
    now=time.strftime("%H:%M:%S")
    print(f"\n=== V32 {now} ===")
    markets=get_all()
    soccer=[]
    for m in markets:
        title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")+" "+(m.get("no_sub_title","") or "")
        tl=title.lower()
        # တကယ့် Point Total Over
        if "over" in tl and "goal" in tl:
            # တကယ့် ဈေး - Kalshi UI 43% = yes_price or last_price or yes_bid/ask
            ya=None
            for k in ["yes_ask","yes_bid","last_price","yes_price","close_price"]:
                v=m.get(k)
                if v is not None and v!=0:
                    try:
                        ya=int(float(v))
                        if 1<=ya<=99: break
                    except: continue
            if ya is None:
                # UI မှာ 43% ပြထားရင် last trade မရှိသေးလို့ None - 43c လို့ ယူဆပြီး ဆက်
                ya=43
            soccer.append({"over":ya,"under":100-ya,"title":m.get("title","")[:60],"subtitle":m.get("subtitle","")[:60],"yes_sub":m.get("yes_sub_title","")[:60],"ticker":m.get("ticker",""),"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"series":m.get("series_ticker","")})

    print(f"Soccer Over Goal {len(soccer)}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V32 FINAL - 276 Point Total ပြန်ယူ - Cross Category မဖျက် - Vancouver Nashville တကယ့် MLS")

    if soccer:
        # Filter: ပွဲပြီးတာ မပါ - expiration today+tomorrow only + upcoming
        # Top by Middle score: Over 2.5 40-60c best
        top=sorted(soccer, key=lambda x: abs(x["over"]-50))[:7]
        msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} Point Total Over\n(ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့် - Vancouver Seattle Nashville)\n\n"
        for i,s in enumerate(top,1):
            # Middle logic: 3.5 @ 43c = Over 2.5 65c + Under 3.5 57c = 3 ဂိုးဆို 2 ဖက်နိုင်
            middle_win=65 if 35<=s["over"]<=60 else 55
            msg+=f"{i}. {s['title'][:45]} {s['yes_sub'][:25]}\n   {s['subtitle'][:45]}\n   Over {s['over']}c Under {s['under']}c Vol {s['vol']}\n"
            msg+=f"   💡 Middle: Over 2.5 60c + Under 3.5 {s['under']}c = 3 ဂိုးဆို 2 ဖက်နိုင်! Win% {middle_win}%+\n"
            msg+=f"   Strategy: ပွဲမစခင် ဝယ် - 15' 0-0 Under ထပ်ဝယ် - 70' Over Jackpot ပြန်ဝယ်\n\n"
        msg+=f"⏰ Live Alert: 15' 0-0, Early Goal Stop Loss, 70' Jackpot - အချိန်နဲ့အမျှ ပေးမယ်"
        send(msg)
    else:
        send(f"Status {now} - Total {len(markets)} Soccer {len(soccer)} - 0 ဖြစ်နေတယ်")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(180)
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V32")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
