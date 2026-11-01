import os, time, requests, threading, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

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

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"\n=== V35 {now} ===")
    markets=get_all()
    soccer=[]
    now_utc=datetime.now(timezone.utc)

    for m in markets:
        series=(m.get("series_ticker","") or "").upper()
        ev=(m.get("event_ticker","") or "").upper()
        title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
        tl=title.lower()

        # Soccer စစ်စစ် ပဲ - Hockey Edmonton, Ottawa, Leon Draisaitl ဖျက်
        if "EDMONTON" in title.upper() or "OTTAWA" in title.upper() or "DRAISAITL" in title.upper() or "STUTZ" in title.upper():
            continue
        if "NHL" in series or "HOCKEY" in series: continue
        # Soccer filter: series or event has SOCCER or title has soccer leagues + goals scored
        is_soccer=False
        if "SOCCER" in series or "SOCCER" in ev: is_soccer=True
        elif any(x in tl for x in ["mls","premier","bundesliga","la liga","serie a","ligue","ucl","champions league","palmeiras","gremio","vancouver","seattle","nashville","necaxa"]) and "goal" in tl:
            is_soccer=True
        if not is_soccer: continue

        # Only Over 2.5 and 3.5 goals scored - for Middle
        if not re.search(r"Over\s+(2\.5|3\.5)\s+goals?\s+scored", title, re.I): continue
        if "1H" in title or "points" in tl or "218.5" in tl: continue

        # Price real
        ya=None
        for k in ["yes_ask","yes_bid","last_price"]:
            v=m.get(k)
            if v and v!=0:
                try: ya=int(float(v)); break
                except: continue
        if ya is None: ya=50
        if not (10<=ya<=90): continue

        # ပွဲပြီးတာ မပါ - expiration > now only, 48h မဖြတ်တော့
        exp_str=m.get("expiration_time","")
        try:
            if exp_str:
                dt=datetime.fromisoformat(exp_str.replace("Z","+00:00"))
                if dt < now_utc: continue
        except: pass

        # Clean team
        team=m.get("title","").split(",")[0][:45] if m.get("title") else ev[:30]
        clean_match=re.search(r"Over\s+\d+\.5\s+goals?\s+scored", title, re.I)
        clean=clean_match.group(0) if clean_match else title[:40]

        soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":ev,"vol":m.get("volume",0),"exp":exp_str[5:16] if exp_str else ""})

    print(f"Total {len(markets)} Soccer 2.5/3.5 {len(soccer)}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V35 FINAL - Soccer စစ်စစ် + Hockey Edmonton ဖျက် + 2.5/3.5 စစ်စစ် + ပွဲပြီးတာ မပါ - 48h filter ဖျက်")

    if soccer:
        from collections import defaultdict
        by_ev=defaultdict(list)
        for s in soccer: by_ev[s["ev"]].append(s)

        middles=[]
        for ev, lst in by_ev.items():
            o25=[x for x in lst if "2.5" in x["clean"]]
            o35=[x for x in lst if "3.5" in x["clean"]]
            if o25 and o35:
                a=o25[0]; b=o35[0]
                middles.append((100-abs(a["over"]-70)-abs(b["over"]-45),a,b,ev))

        middles=sorted(middles, key=lambda x: x[0], reverse=True)[:5]

        if middles:
            msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} ပွဲ Soccer 2.5/3.5 စစ်စစ်\n{len(middles)} Middle အကွက် (ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်)\n\n"
            for i,(score,a,b,ev) in enumerate(middles,1):
                msg+=f"{i}. {a['team'][:45]}\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c (Over 3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n"
                msg+=f"   💡 Middle: 3 ဂိုးဆို 2 ဖက်လုံးနိုင်! Win% 65%+ | ပွဲမစခင် 2 ဖက်ဝယ် - 15' 0-0 Under ထပ်ဝယ် - 70' Jackpot Over ပြန်ဝယ်\n\n"
            send(msg)
        else:
            top=sorted(soccer, key=lambda x: abs(x["over"]-50))[:5]
            msg=f"PRE-MATCH {now} - {len(soccer)} Soccer 2.5/3.5 - Middle pair မတွေ့သေး\n\n"
            for i,s in enumerate(top,1):
                msg+=f"{i}. {s['team'][:40]} {s['clean']} Over {s['over']}c Under {s['under']}c Exp {s['exp']}\n"
            send(msg)
    else:
        send(f"Status {now} - Total {len(markets)} Soccer 2.5/3.5 {len(soccer)} - Soccer စစ်စစ် filter နဲ့ 0 - Series SOCCER ရှာမယ်")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(180)
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V35")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
