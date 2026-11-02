import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg.replace(" Kalshi","KLSH")}, timeout=15)
    except:
        pass

def get_all():
    all_m=[]
    cur=None
    for i in range(18):
        try:
            p={"status":"open","limit":400}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=15)
            if r.status_code==429:
                time.sleep(4)
                continue
            if r.status_code!=200:
                break
            data=r.json()
            ms=data.get("markets",[])
            if not ms:
                break
            all_m.extend(ms)
            cur=data.get("cursor")
            if not cur:
                break
            time.sleep(0.5)
        except:
            break
    return all_m

def analyze():
    try:
        markets=get_all()
        utc_now=datetime.utcnow()
        pst_now=utc_now - timedelta(hours=7)
        tomorrow_pst=pst_now + timedelta(days=1)
        tomorrow_start_pst=datetime(tomorrow_pst.year, tomorrow_pst.month, tomorrow_pst.day, 0,0,0)
        tomorrow_end_pst=tomorrow_start_pst + timedelta(days=1)
        tomorrow_start_utc=tomorrow_start_pst + timedelta(hours=7)
        tomorrow_end_utc=tomorrow_end_pst + timedelta(hours=7)
        tomorrow_str=tomorrow_start_pst.strftime("%m-%d")
        today_str=pst_now.strftime("%m-%d")

        all_soccer=[]
        for m in markets:
            tl=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tll=tl.lower()
            if "both teams to score" in tll:
                continue
            if "edmonton" in tll or "ottawa" in tll:
                continue
            if "wins by more than" in tll:
                continue
            if "over" not in tll or "goals scored" not in tll:
                continue
            if "2.5" not in tll and "3.5" not in tll:
                continue
            exp=m.get("expiration_time","")
            if not exp:
                continue
            try:
                exp_dt=datetime.fromisoformat(exp.replace("Z",""))
                if exp_dt < utc_now:
                    continue
            except:
                continue
            ya=None
            for v in [m.get("yes_ask"), m.get("yes_bid"), m.get("last_price")]:
                if v not in [None,0,"0",""]:
                    try:
                        ya=int(float(v))
                        break
                    except:
                        continue
            if ya is None:
                ya=50
            txt=tll
            team="SOC"
            if "【entity-sassuolo¦canonical_name=sassuolo】" in txt and "【entity-fiorentina¦canonical_name=fiorentina】" in txt:
                team="SAS-FIO"
            elif "【entity-sassuolo¦canonical_name=sassuolo】" in txt:
                team="SAS"
            elif "【entity-fiorentina¦canonical_name=fiorentina】" in txt:
                team="FIO"
            elif "【entity-atalanta¦canonical_name=Atalanta BC】" in txt and "【entity-parma¦canonical_name=parma】" in txt:
                team="ATA-PAR"
            elif "【entity-atalanta¦canonical_name=Atalanta BC】" in txt:
                team="ATA"
            elif "【entity-parma¦canonical_name=parma】" in txt:
                team="PAR"
            elif "【entity-newcastle¦canonical_name=newcastle】" in txt and "【entity-everton¦canonical_name=everton】" in txt:
                team="NEW-EVE"
            elif "【entity-newcastle¦canonical_name=newcastle】" in txt:
                team="NEW"
            elif "【entity-everton¦canonical_name=everton】" in txt:
                team="EVE"
            elif "cruz" in txt:
                team="CZ"
            clean="Over 2.5" if "2.5" in tll else "Over 3.5"
            all_soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"exp_dt":exp_dt,"exp":exp_dt.strftime("%m-%d %H:%M"),"vol":m.get("volume",0) or 0})

        # Tomorrow filter
        tomorrow_games=[s for s in all_soccer if tomorrow_start_utc <= s["exp_dt"] < tomorrow_end_utc]

        print(f"V76 total {len(markets)} all {len(all_soccer)} tomorrow {len(tomorrow_games)} PST {tomorrow_str}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V76 Minimal Smart - Today PST {today_str} Tomorrow PST {tomorrow_str} - Total {len(markets)} AllSoccer {len(all_soccer)} Tomorrow {len(tomorrow_games)}")

        if tomorrow_games:
            by_team={}
            for s in tomorrow_games:
                k=s["team"]
                if k not in by_team:
                    by_team[k]=[]
                by_team[k].append(s)
            middles=[]
            for team, lst in by_team.items():
                o25=[x for x in lst if "2.5" in x["clean"]]
                o35=[x for x in lst if "3.5" in x["clean"]]
                if o25 and o35:
                    a=max(o25, key=lambda x: x["vol"])
                    b=max(o35, key=lambda x: x["vol"])
                    middles.append((a,b))
            if middles:
                msg=f"TOMORROW PST {tomorrow_str} - {len(tomorrow_games)} games - {len(middles)} Middle\n"
                for i,(a,b) in enumerate(middles[:4],1):
                    msg+=f"{i}. {a['team']} {b['exp']} O2.5 {a['over']}c + U3.5 {b['under']}c Vol {b['vol']}\n"
                send(msg)
            else:
                msg=f"TOMORROW PST {tomorrow_str} - {len(tomorrow_games)} Point Total - No middle\n"
                for s in tomorrow_games[:6]:
                    msg+=f"{s['team']} {s['clean']} {s['over']}c {s['exp']} Vol {s['vol']}\n"
                send(msg)
        else:
            # No tomorrow - show next available date
            if all_soccer:
                by_date={}
                for s in all_soccer:
                    pst_exp=s["exp_dt"]-timedelta(hours=7)
                    d=pst_exp.strftime("%m-%d")
                    if d not in by_date:
                        by_date[d]=[]
                    by_date[d].append(s)
                sorted_dates=sorted(by_date.keys())
                next_date=sorted_dates[0]
                next_games=by_date[next_date]
                msg=f"TOMORROW PST {tomorrow_str} - 0 games\nNEXT {next_date} - {len(next_games)} games - Dates {sorted_dates[:4]}\n"
                # Check if screenshot games exist in all_soccer
                has_sas=len([s for s in all_soccer if "SAS" in s["team"] or "FIO" in s["team"]])
                has_new=len([s for s in all_soccer if "NEW" in s["team"]])
                msg+=f"SAS-FIO in 8000: {has_sas} NEW-EVE in 8000: {has_new}\n"
                for s in next_games[:4]:
                    msg+=f"{s['team']} {s['clean']} {s['over']}c {s['exp']} Vol {s['vol']}\n"
                send(msg)
            else:
                send(f"TOMORROW PST {tomorrow_str} - 0 games - AllSoccer 0 in 8000")

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(2)
    send(f"V76 Minimal Smart starting - Tomorrow 11-02 PST")
    while True:
        try:
            analyze()
            time.sleep(180)
        except:
            time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V76 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
