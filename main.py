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

def get_event_map():
    # Event ticker -> Event title (Vancouver vs Seattle)
    ev_map={}
    try:
        for series in ["SOCCERMLS","SOCCER","SOCCEREPL","SOCCERLALIGA","SOCCERUCL"]:
            r=requests.get(f"{BASE}/events", params={"series_ticker":series,"status":"open","limit":200}, timeout=20)
            if r.status_code==200:
                for ev in r.json().get("events",[]):
                    ev_map[ev.get("event_ticker","")]=ev.get("title","") or ev.get("sub_title","")
            time.sleep(0.3)
    except Exception as e:
        print(f"Event map err {e}")
    print(f"Event map {len(ev_map)} events")
    return ev_map

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"\n=== V38 {now} ===")
    markets=get_all()
    ev_map=get_event_map()
    soccer=[]
    now_utc=datetime.now(timezone.utc)

    for m in markets:
        title_raw=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
        tl=title_raw.lower()

        if any(x in tl for x in ["edmonton","ottawa","draisaitl","stutz","【entity-nhl¦canonical_name=NHL】"]): continue
        if "wins by more than" in tl: continue
        if "over" not in tl or "goals scored" not in tl: continue
        if not re.search(r"over\s+(2\.5|3\.5)\s+goals\s+scored", tl): continue

        # Real price - try all fields, if still None skip (not 50c fake)
        ya=None
        for k in ["yes_ask","yes_bid","last_price","yes_price"]:
            v=m.get(k)
            if v not in [None,0,"0",""]:
                try:
                    ya=int(float(v))
                    if 1<=ya<=99: break
                except: continue
        if ya is None: continue # Skip no price, don't fake 50c
        if not (10<=ya<=90): continue

        exp_str=m.get("expiration_time","")
        try:
            if exp_str:
                dt=datetime.fromisoformat(exp_str.replace("Z","+00:00"))
                if dt < now_utc: continue
        except: pass

        ev_ticker=m.get("event_ticker","")
        # Team from event map
        team=ev_map.get(ev_ticker,"")
        if not team:
            # fallback from event_ticker code: VAN-SEA
            team=ev_ticker.split("-")[-2]+" vs "+ev_ticker.split("-")[-1] if "-" in ev_ticker else ev_ticker[:30]
        team=team.replace(" - "," vs ")[:45]
        if len(team)<5: team=ev_ticker[:30]

        clean_match=re.search(r"Over\s+\d+\.5\s+goals\s+scored", title_raw, re.I)
        clean=clean_match.group(0) if clean_match else "Over"

        soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":ev_ticker,"vol":m.get("volume",0),"exp":exp_str[5:16] if exp_str else ""})

    print(f"Total {len(markets)} Soccer {len(soccer)} events {len(ev_map)}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V38 FINAL - Event title map + Team သန့် + Real price only - 410 middle ထဲက အကောင်းဆုံး")

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
                middles.append((100-abs(a["over"]-60)-abs(b["over"]-45)+ (a["vol"]+b["vol"])/100,a,b,ev))

        middles=sorted(middles, key=lambda x: x[0], reverse=True)[:5]

        if middles:
            msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} ပွဲ Soccer 2.5/3.5 စစ်စစ်\n{len(middles)} Middle (ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်)\n\n"
            for i,(score,a,b,ev) in enumerate(middles,1):
                msg+=f"{i}. {a['team']}\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c (Over 3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']} Score {int(score)}\n"
                msg+=f"   💡 3 ဂိုးဆို 2 ဖက်လုံးနိုင်! Win% 65%+ | ပွဲမစခင် 2 ဖက်ဝယ် - 15' 0-0 Under ထပ်ဝယ် - 70' Jackpot Over ပြန်ဝယ်\n\n"
            send(msg)
        else:
            top=sorted(soccer, key=lambda x: x["over"], reverse=True)[:5]
            msg=f"PRE-MATCH {now} - {len(soccer)} ပွဲ Over 2.5/3.5 - Middle pair စောင့်နေတယ်\n\n"
            for i,s in enumerate(top,1):
                msg+=f"{i}. {s['team']} {s['clean']} Over {s['over']}c Exp {s['exp']} Vol {s['vol']}\n"
            send(msg)
    else:
        send(f"Status {now} - Total {len(markets)} Soccer Total {len(soccer)} - Real price filter နဲ့ 0 - Event map {len(ev_map)}")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(180)
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V38")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
