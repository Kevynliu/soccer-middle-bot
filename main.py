import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500].replace(" 【entity-Kalshi¦canonical_name=Kalshi】","KLSH")}, timeout=12)
    except:
        pass

def get_markets_with_retry():
    for attempt in range(5):
        try:
            p={"status":"open","limit":400}
            r=requests.get(f"{BASE}/markets", params=p, timeout=15)
            if r.status_code==429:
                print(f"429 retry {attempt} wait {5*(attempt+1)}s")
                time.sleep(5*(attempt+1))
                continue
            if r.status_code!=200:
                print(f"status {r.status_code}")
                time.sleep(2)
                continue
            return r.json().get("markets",[])
        except Exception as e:
            print(f"err {e}")
            time.sleep(3)
    return []

def analyze():
    try:
        ms=get_markets_with_retry()
        if not ms:
            send(f"V85 API still 429 after retry - will retry in 5 min - Deploy OK but rate limited")
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
        nba_filtered=0
        for m in ms:
            tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "2.5" not in tl and "3.5" not in tl:
                continue
            if "over" not in tl:
                continue
            if "goals scored" not in tl:
                if "wins by over" in tl or "point" in tl:
                    nba_filtered+=1
                continue
            if "edmonton" in tl or "ottawa" in tl or "both teams to score" in tl or "wins by more than" in tl:
                continue
            exp=m.get("expiration_time","")
            try:
                exp_dt=datetime.fromisoformat(exp.replace("Z","")) if exp else None
                if not exp_dt or exp_dt < utc_now:
                    continue
            except:
                continue

            ya=None
            real=False
            for v in [m.get("yes_ask"), m.get("yes_bid"), m.get("last_price")]:
                if v not in [None,0,"0",""]:
                    try:
                        ya=int(float(v))
                        real=True
                        break
                    except:
                        continue
            if ya is None:
                ya=50

            team="SOC"
            if "sassuolo" in tl or "fiorentina" in tl:
                team="SAS-FIO"
            elif "atalanta" in tl or "parma" in tl:
                team="ATA-PAR"
            elif "newcastle" in tl or "everton" in tl:
                team="NEW-EVE"
            elif "cruz" in tl:
                team="CZ"

            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer_pt.append({"over":ya,"clean":clean,"team":team,"exp_dt":exp_dt,"exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),"vol":m.get("volume",0) or 0,"real":real})

        tomorrow_pt=[s for s in soccer_pt if tomorrow_start_utc <= s["exp_dt"] < tomorrow_end_utc]

        print(f"V85 total {len(ms)} pt {len(soccer_pt)} tomorrow {len(tomorrow_pt)}")

        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V85 429 Fixed - Total {len(ms)} PT Soccer {len(soccer_pt)} (filtered {nba_filtered} NBA) Tomorrow PST {tomorrow_str} PT {len(tomorrow_pt)} - Deploy OK!")

        if tomorrow_pt:
            by_team={}
            for s in tomorrow_pt:
                k=s["team"]
                if k not in by_team:
                    by_team[k]=[]
                by_team[k].append(s)
            middles=[]
            for team, lst in by_team.items():
                o25=[x for x in lst if "2.5" in x["clean"]]
                o35=[x for x in lst if "3.5" in x["clean"]]
                if o25 and o35:
                    a=max(o25, key=lambda x: (x["real"], x["vol"]))
                    b=max(o35, key=lambda x: (x["real"], x["vol"]))
                    middles.append((a,b))
            if middles:
                msg=f"TOMORROW PST {tomorrow_str} - {len(tomorrow_pt)} PT - {len(middles)} Middle\n"
                for i,(a,b) in enumerate(middles,1):
                    tag="LIVE" if a["real"] else "EST"
                    msg+=f"{i}. {a['team']} [{tag}] {b['exp_pst']} O2.5 {a['over']}c + U3.5 {b['under']}c Vol {b['vol']}\n"
                send(msg)
            else:
                msg=f"TOMORROW PST {tomorrow_str} - {len(tomorrow_pt)} PT - No middle\n"
                for s in tomorrow_pt[:4]:
                    tag="LIVE" if s["real"] else "EST"
                    msg+=f"{s['team']} [{tag}] {s['clean']} {s['over']}c {s['exp_pst']}\n"
                send(msg)
        else:
            # Show next dates
            by_date={}
            for s in soccer_pt:
                d=(s["exp_dt"]-timedelta(hours=7)).strftime("%m-%d")
                if d not in by_date:
                    by_date[d]=[]
                by_date[d].append(s)
            sd=sorted(by_date.keys())
            msg=f"TOMORROW PST {tomorrow_str} - 0 PT in 400 - Dates {sd[:3]} - Need more markets, will increase after 429 cooldown\n"
            msg+=f"SAS-FIO in 400: {len([s for s in soccer_pt if 'SAS' in s['team']])} - Need 8k-10k scan but need 5min cooldown"
            send(msg)

    except Exception as e:
        print(f"err {e}")
        send(f"V85 Error {str(e)[:200]}")

def bot_loop():
    time.sleep(3)
    send(f"V85 429 Fixed starting - 400 markets + retry - Deploy OK!")
    while True:
        try:
            analyze()
            time.sleep(300)  # 5 min sleep to avoid 429
        except Exception as e:
            print(e)
            time.sleep(300)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V85 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
