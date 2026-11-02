import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        safe=msg.replace(" 【entity-Kalshi¦canonical_name=Kalshi】","KLSH")
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":safe}, timeout=15)
    except:
        pass

def get_events():
    # Get Nov 2 events via events endpoint
    all_e=[]
    try:
        for i in range(5):
            p={"status":"open","limit":200}
            r=requests.get(f"{BASE}/events", params=p, timeout=15)
            if r.status_code!=200:
                break
            data=r.json()
            evs=data.get("events",[])
            all_e.extend(evs)
            print(f"events batch {i} {len(evs)} total {len(all_e)}")
            if len(evs)<200:
                break
            time.sleep(0.5)
    except Exception as e:
        print(f"events err {e}")
    return all_e

def get_markets_for_event(event_ticker):
    try:
        p={"status":"open","limit":100,"event_ticker":event_ticker}
        r=requests.get(f"{BASE}/markets", params=p, timeout=10)
        if r.status_code==200:
            return r.json().get("markets",[])
    except:
        pass
    return []

def get_all_markets():
    all_m=[]
    cur=None
    for i in range(15):
        try:
            p={"status":"open","limit":400}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=15)
            if r.status_code!=200:
                break
            data=r.json()
            ms=data.get("markets",[])
            all_m.extend(ms)
            cur=data.get("cursor")
            if not cur:
                break
            time.sleep(0.3)
        except:
            break
    return all_m

def analyze():
    try:
        utc_now=datetime.utcnow()
        pst_now=utc_now - timedelta(hours=7)
        tomorrow_pst=pst_now + timedelta(days=1)
        tomorrow_str=tomorrow_pst.strftime("%m-%d")
        tomorrow_start_pst=datetime(tomorrow_pst.year, tomorrow_pst.month, tomorrow_pst.day, 0,0,0)
        tomorrow_end_pst=tomorrow_start_pst + timedelta(days=1)
        tomorrow_start_utc=tomorrow_start_pst + timedelta(hours=7)
        tomorrow_end_utc=tomorrow_end_pst + timedelta(hours=7)

        # 1. Get events for Nov 2
        events=get_events()
        nov2_events=[]
        for ev in events:
            title=ev.get("title","") or ev.get("event_ticker","")
            exp_str=ev.get("expiration_time","") or ev.get("expected_expiration_time","")
            if not exp_str:
                continue
            try:
                exp_dt=datetime.fromisoformat(exp_str.replace("Z",""))
                if tomorrow_start_utc <= exp_dt < tomorrow_end_utc:
                    if "sassuolo" in title.lower() or "fiorentina" in title.lower() or "atalanta" in title.lower() or "parma" in title.lower() or "newcastle" in title.lower() or "everton" in title.lower():
                        nov2_events.append(ev)
            except:
                continue

        print(f"Nov2 events filtered {len(nov2_events)} from {len(events)}")

        # 2. Get Point Total markets for those events
        point_markets=[]
        for ev in nov2_events:
            et=ev.get("event_ticker","")
            if not et:
                continue
            ms=get_markets_for_event(et)
            for m in ms:
                ttl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
                if "over" in ttl and "goals" in ttl and ("2.5" in ttl or "3.5" in ttl):
                    point_markets.append(m)
            time.sleep(0.3)

        # 3. Also scan general markets as backup
        all_markets=get_all_markets()
        for m in all_markets:
            ttl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "both teams to score" in ttl:
                continue
            if "edmonton" in ttl or "ottawa" in ttl:
                continue
            if "wins by more than" in ttl:
                continue
            if "over" not in ttl or "goals scored" not in ttl:
                continue
            if "2.5" not in ttl and "3.5" not in ttl:
                continue
            exp=m.get("expiration_time","")
            try:
                exp_dt=datetime.fromisoformat(exp.replace
