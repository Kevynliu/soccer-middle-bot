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
    except Exception as e: print(f"TG err {e}")

def get_soccer_markets():
    all_m=[]
    series_list=["SOCCERMLS","SOCCER","SOCCEREPL","SOCCERLALIGA","SOCCERBUNDES","SOCCERSERIEA","SOCCERUCL"]
    for series in series_list:
        cur=None
        for _ in range(3):
            try:
                p={"status":"open","limit":200,"series_ticker":series}
                if cur: p["cursor"]=cur
                r=requests.get(f"{BASE}/markets", params=p, timeout=20)
                if r.status_code!=200: break
                data=r.json(); ms=data.get("markets",[]); all_m.extend(ms)
                print(f"Series {series}: {len(ms)} markets")
                for mm in ms[:2]:
                    print(f"  RAW SAMPLE: title={mm.get('title','')} ticker={mm.get('ticker','')} yes_bid={mm.get('yes_bid')} yes_ask={mm.get('yes_ask')} last={mm.get('last_price')} vol={mm.get('volume')}")
                cur=data.get("cursor")
                if not cur or len(ms)<200: break
            except Exception as e:
                print(f"Err {series} {e}"); break
    return all_m

def is_upcoming(m):
    if m.get("status","").lower() in ["settled","closed","expired"]: return False
    return True

def analyze():
    now=datetime.now().strftime("%H:%M:%S")
    print(f"\n=== V27 {now} ===")
    markets=get_soccer_markets()
    print(f"Total fetched: {len(markets)}")
    soccer=[]
    raw_samples=[]
    for m in markets:
        if not is_upcoming(m): continue
        title=(m.get("title","")+" "+m.get("subtitle","")).lower()
        # ပိုကျယ်အောင်: over ပါရင် အကုန် ယူ - goal မပါလဲ Point Total ဆို ယူ
        if "over" not in title and "point total" not in title: continue
        # yes price ကို အကုန်စစ်
        ya=m.get("yes_ask") or m.get("yes_bid") or m.get("last_price") or m.get("price") or 0
        try: ya=int(ya)
        except: 
            try: ya=int(float(ya))
            except: continue
        if ya==0: ya=m.get("yes_bid") or 0
        try: ya=int(ya)
        except: continue
        if 1<=ya<=99:
            soccer.append({"over":ya,"under":100-ya,"title":m.get("title",""),"ticker":m.get("ticker",""),"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"series":m.get("series_ticker",""),"raw_yes":m.get("yes_ask")})
        else:
            raw_samples.append(f"{title[:50]} ya={ya}")

    print(f"Point Total Over filtered: {len(soccer)}")
    for s in soccer[:10]:
        print(f"  KEEP {s['over']}c {s['title'][:60]}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V27 FINAL - Filter fix - 20 တွေ့ပြီးပြီ - Point Total Over ရှာနေတယ်")

    if soccer:
        # Top by balanced
        top=sorted(soccer, key=lambda x: abs(x["over"]-50))[:5]
        msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} Point Total (ပွဲပြီးတာ မပါ)\n\nVancouver vs Seattle လို ပွဲတွေ တွေ့ပြီ!\n\n"
        for i,s in enumerate(top,1):
            msg+=f"{i}. {s['title'][:55]}\n   Over {s['over']}c Under {s['under']}c Vol {s['vol']}\n"
            if 35<=s["over"]<=60:
                msg+=f"   💡 Middle: Over 2.5 60c + Under 3.5 {s['under']}c = 3 ဂိုးဆို 2 ဖက်နိုင်! Win% 65%+\n"
                msg+=f"   ပွဲမစခင် ဝယ် - 15' 0-0 ဆို Under ထပ်ဝယ် - 70' Jackpot!\n"
            msg+="\n"
        send(msg)
    else:
        sample_txt="\n".join(raw_samples[:5]) if raw_samples else "no raw"
        send(f"Status {now} - Soccer {len(markets)} တွေ့တယ်, Over filter {len(soccer)} - Raw samples:\n{sample_txt[:800]}\n\nFilter ဖြေနေတယ်")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(180)
        except Exception as e: print(e); send(f"Err {e}"); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V27 running")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
