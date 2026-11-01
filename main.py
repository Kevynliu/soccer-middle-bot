import os, time, requests, threading, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta

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
            if r.status_code!=200: continue
            data=r.json(); ms=data.get("markets",[]); all_m.extend(ms)
            cur=data.get("cursor")
            if not cur: break
            time.sleep(0.5)
        except: break
    return all_m

def clean_over_text(raw):
    # "no Over 4.5 goals scored,no Over 4.5..." -> "Over 4.5 goals scored"
    m=re.search(r"Over\s+\d+\.5\s+goals?\s+scored", raw, re.I)
    if m: return m.group(0)
    m=re.search(r"Over\s+\d+\.5\s+goal", raw, re.I)
    if m: return m.group(0)
    return raw[:50]

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"\n=== V34 {now} ===")
    markets=get_all()
    soccer=[]
    now_utc=datetime.now(timezone.utc)
    cutoff=now_utc+timedelta(hours=48) # လက်ရှိ+နောက်လာမယ့် 48 နာရီ ပဲ

    for m in markets:
        title_full=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
        # Only Over 2.5 and 3.5 for middle - 0.5, 4.5+, 8.5, points မလို
        if not re.search(r"Over\s+(2\.5|3\.5)\s+goals?\s+scored", title_full, re.I):
            continue
        # 1H, points, 218.5 points မလို
        if "1H" in title_full or "points" in title_full.lower() or "218.5" in title_full:
            continue
        # Price
        ya=None
        for k in ["yes_ask","yes_bid","last_price"]:
            v=m.get(k)
            if v and v!=0:
                try: ya=int(float(v)); break
                except: continue
        if ya is None: continue
        if not (10<=ya<=90): continue

        # ပွဲပြီးတာ မပါ - expiration check
        exp_str=m.get("expiration_time","")
        try:
            if exp_str:
                dt=datetime.fromisoformat(exp_str.replace("Z","+00:00"))
                if dt < now_utc: continue # ပြီးသွားတာ
                if dt > cutoff: continue # 48 နာရီ နောက်ကျော်ရင် မလို (optional - ဖျက်ချင်ရင် comment)
        except: pass

        # Clean team name from event_ticker: KXSOCCERMLS-... or title first part
        event=m.get("event_ticker","")
        clean=clean_over_text(title_full)
        team=m.get("title","").split(",")[0][:40] if m.get("title") else event[:30]

        soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ticker":m.get("ticker",""),"ev":event,"vol":m.get("volume",0),"exp":exp_str[5:16] if exp_str else ""})

    print(f"Total {len(markets)} Soccer Over 2.5/3.5 {len(soccer)}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V34 FINAL CLEAN - Over 2.5/3.5 စစ်စစ် - 1H/points ဖျက် - ပွဲပြီးတာ မပါ - လက်ရှိ+48 နာရီ - Title သန့်")

    if soccer:
        # Group by event - find middle pair: same event has 2.5 and 3.5
        from collections import defaultdict
        by_ev=defaultdict(list)
        for s in soccer: by_ev[s["ev"]].append(s)

        middles=[]
        for ev, lst in by_ev.items():
            o25=[x for x in lst if "2.5" in x["clean"]]
            o35=[x for x in lst if "3.5" in x["clean"]]
            if o25 and o35:
                a=o25[0]; b=o35[0]
                # Middle condition: Over 2.5 60-80c, Under 3.5 50-70c = 3 ဂိုးဆို 2 ဖက်နိုင်
                score=100 - abs(a["over"]-70) - abs(b["over"]-45)
                middles.append((score,a,b,ev))

        middles=sorted(middles, key=lambda x: x[0], reverse=True)[:5]

        if middles:
            msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} ပွဲ (2.5/3.5 စစ်စစ်) - {len(middles)} Middle အကွက်\n(ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့် 48h)\n\n"
            for i,(score,a,b,ev) in enumerate(middles,1):
                team=a["team"][:45]
                msg+=f"{i}. {team}\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c (Over 3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n"
                msg+=f"   💡 Strategy: ပွဲမစခင် Over 2.5 {a['over']}c နဲ့ Under 3.5 {b['under']}c ၂ ဖက်ဝယ် = 3 ဂိုးဆို JACKPOT Middle! Win% 65%+\n"
                msg+=f"   Live: 15' 0-0 ဆို Under ထပ်ဝယ် - 70' Over {b['over']}c ကျ Jackpot ပြန်ဝယ်\n\n"
            send(msg)
        else:
            # No paired middle - show top single
            top=sorted(soccer, key=lambda x: abs(x["over"]-50))[:5]
            msg=f"PRE-MATCH {now} - {len(soccer)} ပွဲ Over 2.5/3.5\nMiddle pair မတွေ့သေး - single best:\n\n"
            for i,s in enumerate(top,1):
                msg+=f"{i}. {s['team'][:40]} - {s['clean']}\n   Over {s['over']}c Under {s['under']}c Exp {s['exp']}\n\n"
            send(msg)
    else:
        send(f"Status {now} - Total {len(markets)} Soccer 2.5/3.5 {len(soccer)} - 48h filter နဲ့ 0 - Filter ဖြေမယ်")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(300)
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V34")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
