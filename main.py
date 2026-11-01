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
    # 【entity-Kalshi¦canonical_name=Kalshi】 soccer series - ဒါတွေပဲ တိုက်ရိုက်ရှာ - 4000 limit ပြဿနာ မရှိတော့
    series_list=["SOCCER","SOCCERMLS","SOCCEREPL","SOCCERLALIGA","SOCCERBUNDES","SOCCERSERIEA","SOCCERUCL","SOCCERMLSPLAY"]
    for series in series_list:
        cur=None
        for _ in range(5):
            try:
                p={"status":"open","limit":200,"series_ticker":series}
                if cur: p["cursor"]=cur
                r=requests.get(f"{BASE}/markets", params=p, timeout=20)
                print(f"Series {series} {r.status_code} len {len(r.json().get('markets',[]))}")
                if r.status_code!=200: break
                data=r.json(); ms=data.get("markets",[]); all_m.extend(ms)
                cur=data.get("cursor")
                if not cur or len(ms)<200: break
                time.sleep(0.3)
            except Exception as e:
                print(f"Err {series} {e}"); break
        time.sleep(0.5)
    # fallback - title search
    if len(all_m)<20:
        try:
            p={"status":"open","limit":200}
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code==200:
                for m in r.json().get("markets",[]):
                    t=(m.get("title","")+m.get("subtitle","")).lower()
                    if "over" in t and "goal" in t:
                        all_m.append(m)
        except: pass
    return all_m

def is_upcoming(m):
    if m.get("status","").lower() in ["settled","closed","expired"]: return False
    exp=m.get("expiration_time") or ""
    try:
        if exp:
            dt=datetime.fromisoformat(exp.replace("Z","+00:00"))
            if dt < datetime.now(timezone.utc): return False
    except: pass
    return True

def analyze():
    now=datetime.now().strftime("%H:%M:%S")
    print(f"\n=== V26 {now} ===")
    markets=get_soccer_markets()
    print(f"Total soccer markets fetched: {len(markets)}")
    soccer=[]
    for m in markets:
        if not is_upcoming(m): continue
        title=m.get("title","")
        # Point Total Over
        if "over" not in title.lower(): continue
        if "goal" not in title.lower() and "point total" not in title.lower() and "total" not in title.lower():
            continue
        ya=m.get("yes_ask") or m.get("yes_bid") or m.get("last_price") or 0
        try: ya=int(ya)
        except: continue
        if 5<=ya<=95:
            soccer.append({"over":ya,"under":100-ya,"title":title,"ticker":m.get("ticker",""),"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"series":m.get("series_ticker",""),"exp":m.get("expiration_time","")})
            print(f" {ya}c {100-ya}c {title[:60]} | {m.get('series_ticker','')}")

    print(f"Filtered upcoming Point Total Over: {len(soccer)}")

    # Group by event - find middle: Over 2.5 cheap + Over 3.5 expensive = 3 goals win both
    from collections import defaultdict
    by_ev=defaultdict(list)
    for s in soccer: by_ev[s["ev"]].append(s)

    top=[]
    for ev, lst in by_ev.items():
        # Vancouver vs Seattle မှာ Over 2.5, 3.5, 4.5 ရှိမယ်
        for s in lst:
            score=0
            # Pre-match middle potential: Over 3.5 @ 43% like your screenshot = balanced, good for middle
            if 35<=s["over"]<=60: score+=80  # Best zone
            if 25<=s["over"]<=70: score+=40
            if "3.5" in s["title"]: score+=30
            if "2.5" in s["title"]: score+=20
            if s["vol"]>100: score+=10
            if score>0: top.append((score,s))

    top=sorted(top, key=lambda x: x[0], reverse=True)[:5]

    if not hasattr(analyze,"last"):
        analyze.last=0
        send(f"✅ V26 FINAL Live - Soccer series တိုက်ရိုက် - ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့် - Vancouver vs Seattle 43% တွေ့ပြီလား စမ်းမယ်")
    
    if time.time()-analyze.last>900 or top:  # 15 min
        analyze.last=time.time()
        if top:
            msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} Point Total Over (ပွဲပြီးတာ မပါ)\n\n"
            for i,(score,s) in enumerate(top,1):
                # Find pairing
                pair=[x for x in by_ev[s["ev"]] if x!=s]
                pair_str=""
                if pair:
                    p=pair[0]
                    # Middle: s is Over 3.5 43%, pair is Over 2.5 70% => 3 goals win
                    if "3.5" in s["title"]:
                        msg_pair=f"Over 2.5 {100-p['under']}c? နဲ့ တွဲ Middle"
                    else:
                        msg_pair=""
                else:
                    msg_pair=""

                msg+=f"{i}. {s['title'][:55]}\n"
                msg+=f"   Series {s['series']} | Over {s['over']}c Under {s['under']}c Vol ${s['vol']} Score {score}\n"
                if "3.5" in s["title"] and 35<=s["over"]<=55:
                    msg+=f"   💡 Middle အကွက်: Over 2.5 @ 60-70c + Under 3.5 @{s['under']}c = 3 ဂိုးဆို 2 ဖက်လုံးနိုင်!\n"
                    msg+=f"   Strategy: ပွဲမစခင် Over 2.5 နဲ့ Under 3.5 ၂ ဖက်ဝယ် - 70' 0-0 ဆို Jackpot!\n"
                msg+=f"\n"
            msg+=f"⏰ Live: 15' 0-0 ဆို Under ဈေးတက် - 70' Over ကျ - အချိန်နဲ့အမျှ alert ပေးမယ်"
            send(msg)
        else:
            send(f"Status {now} - Soccer markets {len(markets)} တွေ့တယ်, Point Total Over filter {len(soccer)} - Kalshi API တိုက်ရိုက်ရှာနေတယ်")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(300)
        except Exception as e: print(e); send(f"Err {e}"); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V26 running")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
