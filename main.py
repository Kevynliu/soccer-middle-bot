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

def clean_team(ev, title):
    # KXSOCCERMLS-2025-11-03-VAN-SEA or KXSOCCER-... -> Vancouver vs Seattle
    # event_ticker ထဲကနေ Team ထုတ်
    ev=ev or ""
    # VAN, SEA, NYRB, etc
    m=re.search(r"([A-Z]{2,4})-([A-Z]{2,4})$", ev)
    if m:
        return f"{m.group(1)} vs {m.group(2)}"
    # MLS team codes
    codes={"VAN":"Vancouver","SEA":"Seattle","NYRB":"New York RB","ATL":"Atlanta","NSH":"Nashville","LAFC":"LAFC","LAG":"【entity-LA Galaxy¦canonical_name=LA Galaxy】","MIA":"Miami","PAL":"【entity-Palmeiras¦canonical_name=Palmeiras】","GRE":"Gremio"}
    for k,v in codes.items():
        if k in ev:
            # try find two
            parts=re.findall(r"[A-Z]{3,4}", ev)
            if len(parts)>=2:
                t1=codes.get(parts[-2], parts[-2])
                t2=codes.get(parts[-1], parts[-1])
                return f"{t1} vs {t2}"
    # fallback - title first part before ,
    if title:
        t=title.split(",")[0].split(" Over ")[0][:40]
        if "no " in t.lower(): t=t.lower().replace("no ","").strip()
        if len(t)>5: return t[:40]
    return ev[-20:] if ev else "Soccer Match"

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"\n=== V36 {now} ===")
    markets=get_all()
    soccer=[]
    now_utc=datetime.now(timezone.utc)

    for m in markets:
        series=(m.get("series_ticker","") or "").upper()
        ev=(m.get("event_ticker","") or "")
        title_full=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")

        if "SOCCER" not in series and "SOCCER" not in ev.upper(): continue
        if "NHL" in series or "HOCKEY" in series: continue

        # Only TOTAL goals scored - NOT wins by more than
        # Must be "Over 2.5 goals scored" or "Over 3.5 goals scored" exactly
        # Exclude "wins by more than X goals" = handicap
        if "wins by more than" in title_full.lower(): continue
        if not re.search(r"Over\s+(2\.5|3\.5)\s+goals\s+scored", title_full, re.I): continue

        ya=None
        for k in ["yes_ask","yes_bid","last_price"]:
            v=m.get(k)
            if v and v!=0:
                try: ya=int(float(v)); break
                except: continue
        if ya is None: ya=50
        if not (15<=ya<=85): continue

        exp_str=m.get("expiration_time","")
        try:
            if exp_str:
                dt=datetime.fromisoformat(exp_str.replace("Z","+00:00"))
                if dt < now_utc: continue
        except: pass

        team=clean_team(ev, m.get("title",""))
        clean_match=re.search(r"Over\s+\d+\.5\s+goals\s+scored", title_full, re.I)
        clean=clean_match.group(0) if clean_match else "Over 2.5/3.5"

        soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":ev,"vol":m.get("volume",0),"exp":exp_str[5:16] if exp_str else ""})

    print(f"Total {len(markets)} Soccer Total {len(soccer)}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V36 FINAL - Team နာမည်သန့် + wins by more than Handicap ဖျက် + Over 2.5/3.5 Total စစ်စစ်")

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
                middles.append((100-abs(a["over"]-65)-abs(b["over"]-45),a,b,ev))

        middles=sorted(middles, key=lambda x: x[0], reverse=True)[:5]

        if middles:
            msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} ပွဲ Soccer Total 2.5/3.5\n{len(middles)} Middle (ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်)\n\n"
            for i,(score,a,b,ev) in enumerate(middles,1):
                msg+=f"{i}. {a['team']}\n   {a['clean']} {a['over']}c vs {b['clean']} {b['over']}c\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c (Over 3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n"
                msg+=f"   💡 Middle: 3 ဂိုးဆို 2 ဖက်လုံးနိုင်! Win% 65%+\n   ပွဲမစခင် 2 ဖက်ဝယ် - 15' 0-0 Under ထပ်ဝယ် - 70' Jackpot Over ပြန်ဝယ်\n\n"
            send(msg)
        else:
            # Show top
            top=sorted(soccer, key=lambda x: abs(x["over"]-50))[:5]
            msg=f"PRE-MATCH {now} - {len(soccer)} Soccer Total 2.5/3.5 - Middle pair စောင့်နေတယ်\n\n"
            for i,s in enumerate(top,1):
                msg+=f"{i}. {s['team']} - {s['clean']} Over {s['over']}c Under {s['under']}c Exp {s['exp']}\n"
            send(msg)
    else:
        send(f"Status {now} - Total {len(markets)} Soccer Total {len(soccer)} - Handicap filter နဲ့ 0")

def bot_loop():
    time.sleep(3)
    while True:
        try: analyze(); time.sleep(180)
        except Exception as e: print(e); time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"V36")
    def log_message(self,*a): pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
