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

def clean_team_name(title, ev_ticker, yes_sub):
    # yes_sub = "yes Belgra de Cordoba, Over 2.5..." -> Belgra de Cordoba
    # ev_ticker = KXSOCCER-2025-11-04-BEL-COR or similar
    raw= (yes_sub or title or "") 
    # Remove yes/no and Over part
    raw=re.sub(r"(yes|no)\s+", "", raw, flags=re.I)
    raw=re.split(r"Over\s+\d+\.5", raw, flags=re.I)[0]
    raw=raw.replace(",", "").strip()[:45]
    # If still messy like "Belgra de Cordoba Over", take first 3 words
    if len(raw.split())>4:
        raw=" ".join(raw.split()[:4])
    if len(raw)>=5 and "over" not in raw.lower() and "goal" not in raw.lower():
        return raw
    # Fallback from event_ticker
    if ev_ticker:
        parts=ev_ticker.split("-")
        if len(parts)>=2:
            # last 2 are team codes
            t1=parts[-2][:4]
            t2=parts[-1][:4]
            if len(t1)>=2 and len(t2)>=2:
                return f"{t1} vs {t2}"
    return raw[:30] or "Soccer Match"

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"\n=== V39 {now} ===")
    markets=get_all()
    soccer=[]
    now_utc=datetime.now(timezone.utc)

    for m in markets:
        title_raw=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")+" "+(m.get("no_sub_title","") or "")
        tl=title_raw.lower()

        if any(x in tl for x in ["edmonton","ottawa","draisaitl","stutz"]): continue
        if "wins by more than" in tl: continue
        if "over" not in tl or "goals scored" not in tl: continue
        if not re.search(r"over\s+(2\.5|3\.5)\s+goals\s+scored", tl): continue

        # Price - if None, fallback 50c (Vol 0 markets)
        ya=None
        for k in ["yes_ask","yes_bid","last_price"]:
            v=m.get(k)
            if v not in [None,0,"0",""]:
                try: ya=int(float(v)); break
                except: continue
        if ya is None: ya=50  # Vol 0 = 50c placeholder - keep it!
        if not (10<=ya<=90): continue

        exp_str=m.get("expiration_time","")
        try:
            if exp_str:
                dt=datetime.fromisoformat(exp_str.replace("Z","+00:00"))
                if dt < now_utc: continue
        except: pass

        team=clean_team_name(m.get("title",""), m.get("event_ticker",""), m.get("yes_sub_title","") or m.get("no_sub_title",""))

        clean_match=re.search(r"Over\s+\d+\.5\s+goals\s+scored", title_raw, re.I)
        clean=clean_match.group(0) if clean_match else "Over"

        soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":m.get("event_ticker",""),"vol":m.get("volume",0),"exp":exp_str[5:16] if exp_str else ""})

    print(f"Total {len(markets)} Soccer {len(soccer)}")

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"✅ V39 FINAL - V37 410 ပြန်ယူ + Team သန့် + 50c fallback + Event map မလို - Real 410 middle")

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
            msg=f"🔥 PRE-MATCH MIDDLE {now} - {len(soccer)} ပွဲ Soccer 2.5/3.5\n{len(middles)} Middle (ပွဲပြီးတာ မပါ, လက်ရှိ+နောက်လာမယ့်)\n\n"
            for i,(score,a,b,ev) in enumerate(middles,1):
                msg+=f"{i}. {a['team']}\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c (Over 3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n   💡 3 ဂိုးဆို 2 ဖက်လုံးနိုင်! Win% 65%+ | ပွဲမစခင် 2 ဖက်ဝယ် - 15' 0-0 Under ထပ်ဝယ် - 70' Jackpot Over ပြန်ဝယ်\n\n"
            send(msg)
        else:
           
