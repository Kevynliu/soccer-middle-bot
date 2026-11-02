import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500].replace("Kalshi","KLSH")}, timeout=12)
    except:
        pass

def get_markets_cursor(total_want=3000):
    all_ms=[]
    cursor=None
    tries=0
    while len(all_ms) < total_want and tries < 20:
        try:
            p={"status":"open","limit":200}
            if cursor:
                p["cursor"]=cursor
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code==429:
                print("429 wait 60s")
                time.sleep(60)
                r=requests.get(f"{BASE}/markets", params=p, timeout=20)
                if r.status_code==429:
                    send(f"V91 429 after {len(all_ms)} markets - will continue next cycle")
                    break
            if r.status_code!=200:
                print(f"API {r.status_code}")
                time.sleep(2)
                tries+=1
                continue
            data=r.json()
            batch=data.get("markets",[])
            all_ms.extend(batch)
            cursor=data.get("cursor")
            if not cursor or not batch:
                break
            time.sleep(0.6)  # avoid 429
        except Exception as e:
            print(f"err {e}")
            time.sleep(3)
            tries+=1
    return all_ms

def analyze():
    ms=get_markets_cursor(total_want=3000)
    if ms is None:
        return
    if not ms:
        return

    utc_now=datetime.utcnow()
    pst_now=utc_now - timedelta(hours=7)
    tomorrow_pst=pst_now + timedelta(days=1)
    tomorrow_start_pst=datetime(tomorrow_pst.year, tomorrow_pst.month, tomorrow_pst.day, 0,0,0)
    tomorrow_end_pst=tomorrow_start_pst + timedelta(days=1)
    tomorrow_start_utc=tomorrow_start_pst + timedelta(hours=7)
    tomorrow_end_utc=tomorrow_end_pst + timedelta(hours=7)
    tomorrow_str=tomorrow_start_pst.strftime("%m-%d")

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
        team="SOC"
        if "sassuolo" in tl: team="SAS-FIO" if "fiorentina" in tl else "SAS"
        elif "fiorentina" in tl: team="FIO"
        elif "newcastle" in tl: team="NEW-EVE" if "everton" in tl else "NEW"
        elif "everton" in tl: team="EVE"
        elif "atalanta" in tl: team="ATA-PAR" if "parma" in tl else "ATA"
        elif "parma" in tl: team="PAR"
        elif "cruz" in tl: team="CZ"
        elif "lorient" in tl: team="LOR"
        elif "brest" in tl: team="BRE"
        clean="Over 2.5" if "2.5" in tl else "Over 3.5"
        under=100-ya
        soccer_pt.append({"team":team,"clean":clean,"over":ya,"under":under,"exp_dt":exp_dt,"exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),"vol":m.get("volume",0) or 0,"real":real})

    tomorrow_pt=[s for s in soccer_pt if tomorrow_start_utc <= s["exp_dt"] < tomorrow_end_utc]
    today_pt=[s for s in soccer_pt if (pst_now.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(hours=7)) <= s["exp_dt"] < tomorrow_start_utc]

    if not hasattr(analyze,"first"):
        analyze.first=True
        by_date={}
        for s in soccer_pt:
            d=(s["exp_dt"]-timedelta(hours=7)).strftime("%m-%d")
            by_date[d]=by_date.get(d,0)+1
        sd=sorted(by_date.items())
        send(f"V91 Deep 3000 - Deploy OK!\nToday {pst_now.strftime('%m-%d')} {len(today_pt)} Tomorrow {tomorrow_str} {len(tomorrow_pt)} PT\nTotal {len(ms)} -> Soccer PT {len(soccer_pt)}\nDates: {sd[:6]}")

    if tomorrow_pt:
        by_team={}
        for s in tomorrow_pt:
            by_team.setdefault(s["team"], []).append(s)
        msg=f"TOMORROW PST {tomorrow_str} - {len(tomorrow_pt)} PT - MIDDLE SCAN\n"
        found_middle=0
        for team,lst in by_team.items():
            o25=[x for x in lst if "2.5" in x["clean"]]
            o35=[x for x in lst if "3.5" in x["clean"]]
            if o25 and o35:
                a=max(o25, key=lambda x: (x["real"], x["vol"]))
                b=max(o35, key=lambda x: (x["real"], x["vol"]))
                found_middle+=1
                tag_a="LIVE" if a["real"] else "EST"
                tag_b="LIVE" if b["real"] else "EST"
                msg+=f"{team}: O2.5 {a['over']}c [{tag_a}] + U3.5 {b['under']}c [{tag_b}] = Profit {a['over']+b['under']-100} if 3 goals! {a['exp_pst']} Vol {a['vol']}\n"
        if found_middle==0:
            msg+=f"No middle yet (need O2.5+U3.5 same team)\n"
            for s in tomorrow_pt[:6]:
                tag="LIVE" if s["real"] else "EST"
                msg+=f"{s['team']} [{tag}] {s['clean']} {s['over']}c {s['exp_pst']} Vol {s['vol']}\n"
        send(msg)
    else:
        by_date={}
        for s in soccer_pt:
            d=(s["exp_dt"]-timedelta(hours=7)).strftime("%m-%d")
            by_date.setdefault(d, []).append(s)
        sd=sorted(by_date.keys())
        msg=f"TOMORROW {tomorrow_str} - 0 PT in {len(ms)} - NEXT {sd[0] if sd else 'none'} {len(by_date.get(sd[0],[])) if sd else 0} games Dates {sd[:4]}\n"
        # Check SAS-FIO
        sas=[s for s in soccer_pt if "SAS" in s["team"]]
        msg+=f"SAS-FIO in {len(ms)}: {len(sas)} - Sample {sas[0]['exp_pst'] if sas else 'none'}\nNote: 11-03 PT may list closer to game time, will scan 6000 next if needed"
        send(msg)

def bot_loop():
    time.sleep(5)
    send(f"V91 Deep 3000 starting - 3000 markets + cursor + PST fix - Deploy OK if you see this!")
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
        self.wfile.write(b"V91 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
