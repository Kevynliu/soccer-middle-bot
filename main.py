import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500].replace("【entity-Kalshi¦canonical_name=Kalshi】","【entity-KLSH¦canonical_name=Kalshi】")}, timeout=12)
    except:
        pass

def get_markets(total=3000):
    all_ms=[]
    cursor=None
    while len(all_ms) < total:
        try:
            p={"status":"open","limit":200}
            if cursor: p["cursor"]=cursor
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code==429:
                time.sleep(60)
                r=requests.get(f"{BASE}/markets", params=p, timeout=20)
                if r.status_code==429:
                    break
            if r.status_code!=200:
                time.sleep(2)
                continue
            d=r.json()
            batch=d.get("markets",[])
            all_ms.extend(batch)
            cursor=d.get("cursor")
            if not cursor or not batch:
                break
            time.sleep(0.5)
        except:
            time.sleep(3)
            break
    return all_ms

def analyze():
    ms=get_markets(total=3000)
    if not ms:
        return
    utc_now=datetime.utcnow()
    pst_now=utc_now - timedelta(hours=7)
    tomorrow_pst=pst_now + timedelta(days=1)
    ts_pst=datetime(tomorrow_pst.year, tomorrow_pst.month, tomorrow_pst.day, 0,0,0)
    te_pst=ts_pst + timedelta(days=1)
    ts_utc=ts_pst + timedelta(hours=7)
    te_utc=te_pst + timedelta(hours=7)
    tomorrow_str=ts_pst.strftime("%m-%d")
    today_str=pst_now.strftime("%m-%d")

    soccer_pt=[]
    for m in ms:
        tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
        if "2.5" not in tl and "3.5" not in tl: continue
        if "over" not in tl: continue
        if "goals scored" not in tl: continue
        if "edmonton" in tl or "ottawa" in tl or "both teams to score" in tl: continue
        exp=m.get("expiration_time","")
        try:
            exp_dt=datetime.fromisoformat(exp.replace("Z","")) if exp else None
            if not exp_dt or exp_dt < utc_now: continue
        except:
            continue
        ya=50
        real=False
        for v in [m.get("yes_ask"), m.get("yes_bid"), m.get("last_price")]:
            if v not in [None,0,""]:
                try:
                    ya=int(float(v))
                    real=True
                    break
                except:
                    continue
        # Clean team
        team="SOC"
        t=tl
        if "sassuolo" in t and "fiorentina" in t: team="SAS-FIO"
        elif "sassuolo" in t: team="SAS"
        elif "fiorentina" in t: team="FIO"
        elif "newcastle" in t: team="NEW-EVE" if "everton" in t else "NEW"
        elif "everton" in t: team="EVE"
        elif "atalanta" in t: team="ATA"
        elif "parma" in t: team="PAR"
        elif "cruz azul" in t: team="CZ"
        elif "lorient" in t: team="LOR"
        elif "brest" in t: team="BRE"
        elif "inter miami" in t: team="MIA"
        clean="Over 2.5" if "2.5" in t else "Over 3.5"
        soccer_pt.append({"team":team,"clean":clean,"over":ya,"under":100-ya,"exp_dt":exp_dt,"exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),"vol":m.get("volume",0) or 0,"real":real})

    tomorrow_pt=[s for s in soccer_pt if ts_utc <= s["exp_dt"] < te_utc]

    # DAILY SUMMARY - 1 per cycle
    if not hasattr(analyze,"first"):
        analyze.first=True
        by_date={}
        for s in soccer_pt:
            d=(s["exp_dt"]-timedelta(hours=7)).strftime("%m-%d")
            by_date[d]=by_date.get(d,0)+1
        sd=sorted(by_date.items())
        send(f"V92 FINAL AUTO - Deploy OK!\nToday {today_str} Tomorrow {tomorrow_str} {len(tomorrow_pt)} PT\nTotal {len(ms)} -> Soccer PT {len(soccer_pt)}\nDates: {sd[:6]}\nAuto-alert active - will notify when {tomorrow_str} PT markets list!")

    # TOMORROW LOGIC
    if tomorrow_pt:
        by_team={}
        for s in tomorrow_pt:
            by_team.setdefault(s["team"], []).append(s)
        msg=f"🔥 TOMORROW PST {tomorrow_str} - {len(tomorrow_pt)} PT FOUND! 🔥\n"
        middles=0
        for team,lst in by_team.items():
            o25=[x for x in lst if "2.5" in x["clean"]]
            o35=[x for x in lst if "3.5" in x["clean"]]
            if o25 and o35:
                a=max(o25, key=lambda x: (x["real"], x["vol"]))
                b=max(o35, key=lambda x: (x["real"], x["vol"]))
                middles+=1
                tag_a="LIVE" if a["real"] else "EST"
                tag_b="LIVE" if b["real"] else "EST"
                profit=a["over"]+b["under"]-100
                # 3 goals = both win
                msg+=f"\n✅ MIDDLE {team}: O2.5 {a['over']}c [{tag_a}] + U3.5 {b['under']}c [{tag_b}]\n💰 Profit if 3 goals: {profit}c | Vol {a['vol']}/{b['vol']}\n⏰ {a['exp_pst']}\n"
        if middles==0:
            msg+=f"No middle yet (need O2.5 + U3.5 same team)\n"
            for s in tomorrow_pt[:8]:
                tag="LIVE" if s["real"] else "EST"
                msg+=f"{s['team']} [{tag}] {s['clean']} {s['over']}c Vol {s['vol']} {s['exp_pst']}\n"
        else:
            msg+=f"\n🎯 {middles} MIDDLE(s) FOUND - 3 goals = both win!"
        send(msg)
    else:
        # No tomorrow yet - smart message, only send if new date
        by_date={}
        for s in soccer_pt:
            d=(s["exp_dt"]-timedelta(hours=7)).strftime("%m-%d")
            by_date.setdefault(d, []).append(s)
        sd=sorted(by_date.keys())
        # Only alert once per hour when 0
        if not hasattr(analyze,"last_zero") or time.time()-analyze.last_zero > 3600:
            analyze.last_zero=time.time()
            msg=f"TOMORROW {tomorrow_str} - 0 PT in {len(ms)} (NEXT {sd[0] if sd else 'none'} {len(by_date.get(sd[0],[])) if sd else 0} games)\nDates {sd[:4]} - KLSH PT lists close to game time, checking every 5min\nSAS-FIO in {len(ms)}: {len([s for s in soccer_pt if 'SAS' in s['team']])} Sample { [s['exp_pst'] for s in soccer_pt if 'SAS' in s['team']][:1] }"
            send(msg)

def bot_loop():
    time.sleep(5)
    send(f"V92 FINAL AUTO starting - 3000 markets + Auto-alert for { (datetime.utcnow()-timedelta(hours=7)+timedelta(days=1)).strftime('%m-%d')} PST - Deploy OK!")
    while True:
        try:
            analyze()
            time.sleep(300)
        except Exception as e:
            print(e)
            time.sleep(300)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V92 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
