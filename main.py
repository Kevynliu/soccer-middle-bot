import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        r=requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=20)
        print(f"TG {r.status_code}")
    except: pass

def get_soccer():
    all_m=[]
    series_list=["SOCCERMLS","SOCCER","SOCCEREPL","SOCCERLALIGA","SOCCERUCL","SOCCERBUNDES","SOCCERSERIEA"]
    for series in series_list:
        cur=None
        for _ in range(5):
            try:
                p={"status":"open","limit":200,"series_ticker":series}
                if cur: p["cursor"]=cur
                r=requests.get(f"{BASE}/markets", params=p, timeout=20)
                if r.status_code!=200:
                    print(f"Series {series} fail {r.status_code}"); break
                data=r.json(); ms=data.get("markets",[])
                print(f"Series {series} got {len(ms)}")
                for mm in ms[:3]:
                    print(f"  {mm.get('title','')[:50]} | yes_bid={mm.get('yes_bid')} yes_ask={mm.get('yes_ask')} last={mm.get('last_price')} ticker={mm.get('ticker')}")
                all_m.extend(ms)
                cur=data.get("cursor")
                if not cur: break
                time.sleep(0.4)
            except Exception as e: print(e); break
    return all_m

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"\n=== V31 {now} ===")
    markets=get_soccer()
    soccer=[]
    for m in markets:
        if "CROSSCATEGORY" in (m.get("series_ticker","")+m.get("ticker","")): continue
        title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")
        if "over" not in title.lower(): continue
        # တကယ့် ဈေး - fallback မလုပ်
        ya=None
        for k in ["yes_ask","yes_bid","last_price"]:
            v=m.get(k)
            if v is not None and v!=0:
                try:
                    ya=int(float(v))
                    if 1<=ya<=99: break
                except: continue
        if ya is None: continue
        if m.get("status","").lower() not in ["open","active",""]: continue
        soccer.append({"over":ya,"under":100-ya,"title":m.get("title",""),"subtitle":m.get("subtitle",""),"ticker":m.get("ticker",""),"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"series":m.get("series_ticker",""),"exp":m.get("expiration_time","")})

    print(f"Soccer real {len(soccer)}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V31 FINAL - SOCCER series only - Cross Category ဖျက် - တကယ့် Vancouver 43% ဈေး")

    if soccer:
        top=sorted(soccer, key=lambda x: abs(x["over"]-50))[:5]
        msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} Point Total Over (ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်)\nVancouver vs Seattle 43% လို တကယ့် MLS\n\n"
        for i,s in enumerate(top,1):
            msg+=f"{i}. {s['title'][:50]}\n   {s['subtitle'][:40]}\n   Over {s['over']}c Under {s['under']}c Vol {s['vol']} Series {s['series']}\n"
            if 35<=s["over"]<=60:
                msg+=f"   💡 Middle: Over 2.5 60c + Under 3.5 {s['under']}c = 3 ဂိုးဆို 2 ဖက်နိုင်! Win% 65%+\n"
                msg+=f"   ပွဲမစခင် ဝယ် - 15' 0-0 Under ထပ်ဝယ် - 70' Jackpot Over ပြန်ဝယ်\n"
            msg+="\n"
        send(msg)
    else:
        send(f"Status {now} - Soccer series {len(markets)} markets, Point Total Over {len(soccer)} - Series filter နဲ့ ရှာတာ 0 - Kalshi MLS market ပိတ်သွားပြီလား - Log စစ်မယ်")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(180)
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V31")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
