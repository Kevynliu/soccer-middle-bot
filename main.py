import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=20)
    except:
        pass

def get_all():
    all_m=[]
    cur=None
    for i in range(15):
        try:
            p={"status":"open","limit":400}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code!=200:
                continue
            data=r.json()
            ms=data.get("markets",[])
            all_m.extend(ms)
            cur=data.get("cursor")
            if not cur:
                break
            time.sleep(0.5)
        except:
            break
    return all_m

def clean_team(ev, title, yes_sub):
    # Try yes_sub first: "【entity-Cruz Azul¦canonical_name=Cruz Azul】 vs Tijuana Over 2.5" -> 【entity-Cruz Azul¦canonical_name=Cruz Azul】 vs Tijuana
    raw=(yes_sub or title or "")
    raw=raw.replace("yes","").replace("no","").strip()
    # Split by Over
    if "Over" in raw:
        raw=raw.split("Over")[0]
    # Remove Both Teams
    if "Both Teams" in raw:
        return ""
    raw=raw.replace(",","").strip()[:40]
    # If still messy like "【entity-Cruz Azul¦canonical_name=Cruz Azul】 Los Angeles F Miami" (3 teams), take first 2 words vs last 2
    words=raw.split()
    if len(words) >= 4 and "Los" in raw:
        # 【entity-Cruz Azul¦canonical_name=Cruz Azul】 Los Angeles F Miami -> 【entity-Cruz Azul¦canonical_name=Cruz Azul】 vs Miami?
        return f"{words[0]} {words[1]} vs {words[-1]}"[:35]
    if len(raw) >= 5 and "KX" not in raw.upper() and "CROSS" not in raw.upper():
        return raw[:35]
    # Fallback ev: KXSOCCER-...-CRUZ-TIJ -> Cruz vs Tij
    if ev and "-" in ev:
        parts=ev.split("-")
        if len(parts) >= 2:
            t1=parts[-2]
            t2=parts[-1]
            mapping={"CRUZ":"【entity-Cruz Azul¦canonical_name=Cruz Azul】","TIJ":"Tijuana","VAN":"Vancouver","SEA":"Seattle","QUILM":"Quilmes","LANUS":"Lanus","MIA":"Miami","LAFC":"LAFC"}
            t1=mapping.get(t1.upper(), t1)
            t2=mapping.get(t2.upper(), t2)
            if len(t1)>=2 and len(t2)>=2:
                return f"{t1} vs {t2}"
    return raw[:30] if raw else "Soccer"

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V48 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.now(timezone.utc)
        for m in markets:
            series=(m.get("series_ticker","") or "").upper()
            ev=(m.get("event_ticker","") or "")
            ev_up=ev.upper()
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
            # No filter CrossCategory - Soccer Point Total is in CrossCategory!
            if "both teams to score" in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl or "lendeborg" in tl or "austin reaves" in tl or "yaxel" in tl:
                continue
            if "wins by more than" in tl:
                continue
            if "over" not in tl or "goals scored" not in tl:
                continue
            if "2.5" not in tl and "3.5" not in tl:
                continue
            ya=None
            for k in ["yes_ask","yes_bid","last_price"]:
                v=m.get(k)
                if v not in [None,0,"0",""]:
                    try:
                        ya=int(float(v))
                        break
                    except:
                        continue
            if ya is None:
                ya=50
            if not (5 <= ya <= 95):
                continue
            exp=m.get("expiration_time","")
            try:
                if exp:
                    dt=datetime.fromisoformat(exp.replace("Z","+00:00"))
                    if dt < now_utc:
                        continue
            except:
                pass
            team=clean_team(ev, m.get("title",""), m.get("yes_sub_title",""))
            if not team or "CROSS" in team.upper():
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":ev,"vol":m.get("volume",0),"exp":exp[5:16] if exp else ""})

        print(f"total {len(markets)} soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V48 FINAL CLEAN Live - CrossCategory ပြန်ယူ + Team သန့် - Total {len(markets)} Soccer {len(soccer)}")

        if soccer:
            by_ev={}
            for s in soccer:
                ev=s["ev"]
                if ev not in by_ev:
                    by_ev[ev]=[]
                by_ev[ev].append(s)

            middles=[]
            for ev, lst in by_ev.items():
                o25=[x for x in lst if "2.5" in x["clean"]]
                o35=[x for x in lst if "3.5" in x["clean"]]
                if o25 and o35:
                    middles.append((o25[0],o35
