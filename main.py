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

def get_all():
    all_m=[]; cur=None
    for i in range(20): # 20*250 = 5000 markets
        try:
            p={"status":"open","limit":250}
            if cur: p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=25)
            print(f"Fetch {i} status {r.status_code} count {len(r.json().get('markets',[])) if r.status_code==200 else 0}")
            if r.status_code!=200:
                print(f"Body {r.text[:200]}")
                time.sleep(2); continue
            data=r.json(); ms=data.get("markets",[]); 
            all_m.extend(ms)
            cur=data.get("cursor")
            if not cur: break
            time.sleep(0.5)
        except Exception as e:
            print(f"Fetch err {e}"); time.sleep(2)
    return all_m

def analyze():
    now=datetime.now().strftime("%H:%M:%S")
    print(f"\n=== V28 {now} ===")
    markets=get_all()
    print(f"Total fetched {len(markets)}")
    soccer=[]
    samples=[]
    for m in markets:
        ev=(m.get("event_ticker","")+" "+m.get("series_ticker","")+" "+m.get("ticker","")).upper()
        title=m.get("title","") or ""
        # Soccer event_ticker has SOCCER
        if "SOCCER" not in ev: continue
        # Point Total or Over
        if "OVER" not in title.upper() and "POINT TOTAL" not in title.upper() and "TOTAL" not in (m.get("subtitle","").upper()):
            # Still keep for debug
            if len(samples)<5:
                samples.append(f"{title[:50]} ev={ev}")
            continue
        # Price - check all fields
        ya=None
        for k in ["yes_ask","yes_bid","last_price","price","yes_price"]:
            v=m.get(k)
            if v is not None:
                try:
                    ya=int(v)
                    break
                except:
                    try: ya=int(float(v)); break
                    except: continue
        if ya is None: continue
        if 1<=ya<=99:
            soccer.append({"over":ya,"under":100-ya,"title":title,"ticker":m.get("ticker",""),"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"series":m.get("series_ticker","")})
            print(f" KEEP {ya}c {title[:60]} ev={ev}")

    print(f"Soccer Point Total {len(soccer)} samples {samples}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V28 FINAL - Full 5000 scan - SOCCER event_ticker filter - Vancouver 43% ရှာမယ်")

    if soccer:
        top=sorted(soccer, key=lambda x: abs(x["over"]-43))[:5] # 43% is sweet spot like screenshot
        msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} Point Total Over (ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်)\n\n"
        for i,s in enumerate(top,1):
            msg+=f"{i}. {s['title'][:55]}\n   {s['series']} {s['ev'][-20:]} Over {s['over']}c Under {s['under']}c Vol {s['vol']}\n"
            if 35<=s["over"]<=60:
                msg+=f"   💡 Middle အကွက်: Over 2.5 60c + Under 3.5 {s['under']}c = 3 ဂိုးဆို 2 ဖက်နိုင်! Win% 65%+\n"
                msg+=f"   ပွဲမစခင် ဝယ်ထား - 15' 0-0 ဆို Under ထပ်ဝယ် - 70' Jackpot!\n"
            msg+="\n"
        send(msg)
    else:
        s_txt="\n".join(samples[:3]) if samples else "No soccer samples"
        send(f"Status {now} - Total {len(markets)} markets, Soccer Point Total {len(soccer)}\nSamples:\n{s_txt}\n\nFull scan {len(markets)} - Filter ထပ်ပြင်မယ်")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(180)
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V28 running")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
