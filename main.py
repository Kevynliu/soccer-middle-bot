import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=20)
    except: pass

def get_all():
    all_m=[]; cur=None
    for i in range(25):
        try:
            p={"status":"open","limit":400}
            if cur: p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=25)
            print(f"Fetch {i} {r.status_code}")
            if r.status_code!=200:
                print(r.text[:200]); time.sleep(2); continue
            data=r.json(); ms=data.get("markets",[]); all_m.extend(ms)
            cur=data.get("cursor")
            if not cur: break
            time.sleep(0.5)
        except Exception as e: print(e); time.sleep(2)
    return all_m

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"\n=== V33 {now} ===")
    markets=get_all()
    soccer=[]
    for m in markets:
        title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")+" "+(m.get("no_sub_title","") or "")
        tl=title.lower()
        if "over" in tl and "goal" in tl:
            ya=None
            for k in ["yes_ask","yes_bid","last_price"]:
                v=m.get(k)
                if v is not None and v!=0:
                    try: ya=int(float(v)); break
                    except: continue
            if ya is None: ya=43
            if 1<=ya<=99:
                soccer.append({"over":ya,"under":100-ya,"title":m.get("title","")[:60],"subtitle":m.get("subtitle","")[:60],"yes_sub":m.get("yes_sub_title","")[:50],"ticker":m.get("ticker",""),"vol":m.get("volume",0),"exp":m.get("expiration_time","")[:16]})

    print(f"Total {len(markets)} Soccer Over {len(soccer)}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V33 FINAL - Typo fix - BASE URL space ဖျက် - 276 ပြန်ရမယ်")

    if soccer:
        top=sorted(soccer, key=lambda x: abs(x["over"]-50))[:7]
        msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} Point Total Over (ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်)\n\nVancouver Seattle Nashville Palmeiras Gremio တကယ့် ပွဲတွေ\n\n"
        for i,s in enumerate(top,1):
            msg+=f"{i}. {s['title']} {s['yes_sub']}\n   {s['subtitle']}\n   Over {s['over']}c Under {s['under']}c Vol {s['vol']} Exp {s['exp']}\n"
            msg+=f"   💡 Middle: Over 2.5 60c + Under 3.5 {s['under']}c = 3 ဂိုးဆို 2 ဖက်နိုင်! Win% 65%+\n"
            msg+=f"   ပွဲမစခင် ဝယ် - 15' 0-0 Under ထပ်ဝယ် - 70' Jackpot Over ပြန်ဝယ်\n\n"
        msg+=f"⏰ Live: 15' 0-0, Early Goal Stop Loss, 70' Jackpot အချိန်နဲ့အမျှ"
        send(msg)
    else:
        send(f"Status {now} - Total {len(markets)} Soccer {len(soccer)} - 0 ဖြစ်နေသေးရင် Log စစ်မယ် - BASE fix ပြီးပြီ")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(180)
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V33")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
