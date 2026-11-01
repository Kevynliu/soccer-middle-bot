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
    print(f"\n=== V37 {now} ===")
    markets=get_all()
    soccer=[]
    now_utc=datetime.now(timezone.utc)

    for m in markets:
        title_raw=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")+" "+(m.get("no_sub_title","") or "")
        tl=title_raw.lower()

        # Hockey ဖျက်
        if any(x in tl for x in ["edmonton","ottawa","draisaitl","stutz","nhl"]): continue
        # Handicap "wins by more than X goals" ဖျက် - Total ဂိုးပေါင်း မဟုတ်ဘူး
        if "wins by more than" in tl: continue
        # Only Over X goals scored
        if "over" not in tl or "goals scored" not in tl: continue
        # Only 2.5 and 3.5 for middle - 0.5,1.5,4.5,7.5 မလို
        if not re.search(r"over\s+(2\.5|3\.5)\s+goals\s+scored", tl): continue

        # Price
        ya=None
        for k in ["yes_ask","yes_bid","last_price"]:
            v=m.get(k)
            if v and v!=0:
                try: ya=int(float(v)); break
                except: continue
        if ya is None: ya=50
        if not (15<=ya<=85): continue

        # ပွဲပြီးတာ မပါ
        exp_str=m.get("expiration_time","")
        try:
            if exp_str:
                dt=datetime.fromisoformat(exp_str.replace("Z","+00:00"))
                if dt < now_utc: continue
        except: pass

        # Team name clean - "yes Belgrano de Cordoba Over 2.5..." -> "Belgrano de Cordoba"
        team="Soccer"
        # yes sub title has team + Over
        yst=m.get("yes_sub_title","") or m.get("no_sub_title","") or ""
        # Remove Over part
        team_match=re.split(r"Over\s+\d+\.5", yst, flags=re.I)[0]
        team=team_match.replace("yes","").replace("no","").strip()[:45]
        if len(team)<3:
            team=m.get("title","")[:45].split(",")[0][:45]
            team=team.replace("no","").replace("yes","").strip()

        clean_match=re.search(r"Over\s+\d+\.5\s+goals\s+scored", title_raw, re.I)
        clean=clean_match.group(0) if clean_match else "Over 2.5"

        soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"exp":exp_str[5:16] if exp_str else ""})

    print(f"Total {len(markets)} Soccer 2.5/3.5 {len(soccer)}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V37 FINAL - V35 289 ပြန်ယူ + Over 2.5/3.5 စစ်စစ် + wins by more than ဖျက် + Hockey ဖျက် + Team သန့်")

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
                middles.append((100-abs(a["over"]-60)-abs(b["over"]-45),a,b,ev))

        middles=sorted(middles, key=lambda x: x[0], reverse=True)[:5]

        if middles:
            msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} ပွဲ Over 2.5/3.5 စစ်စစ်\n{len(middles)} Middle (ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်)\n\n"
            for i,(score,a,b,ev) in enumerate(middles,1):
                msg+=f"{i}. {a['team']}\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c (Over 3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n   💡 3 ဂိုးဆို 2 ဖက်လုံးနိုင်! Win% 65%+ | ပွဲမစခင် 2 ဖက်ဝယ် - 15' 0-0 Under ထပ်ဝယ် - 70' Jackpot Over ပြန်ဝယ်\n\n"
            send(msg)
        else:
            # Show top single but team clean
            top=sorted(soccer, key=lambda x: abs(x["over"]-50))[:5]
            msg=f"PRE-MATCH {now} - {len(soccer)} ပွဲ Soccer Over 2.5/3.5 - Middle pair စောင့်နေတယ် - Team သန့်\n\n"
            for i,s in enumerate(top,1):
                msg+=f"{i}. {s['team']} - {s['clean']} Over {s['over']}c Under {s['under']}c Exp {s['exp']}\n"
            send(msg)
    else:
        send(f"Status {now} - Total {len(markets)} Soccer Total {len(soccer)} - 0 ဖြစ်နေတယ် - Filter စစ်မယ်")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(180)
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V37")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
