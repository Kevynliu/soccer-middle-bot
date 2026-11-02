import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500].replace(" 【entity-Kalshi¦canonical_name=Kalshi】","KLSH")}, timeout=15)
    except:
        pass

def get_all():
    all_m=[]
    cur=None
    for i in range(40):  # 16k markets
        try:
            p={"status":"open","limit":400}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code==429:
                time.sleep(5)
                continue
            if r.status_code!=200:
                print(f"batch {i} {r.status_code}")
                break
            data=r.json()
            ms=data.get("markets",[])
            if not ms:
                break
            all_m.extend(ms)
            cur=data.get("cursor")
            print(f"batch {i} got {len(ms)} total {len(all_m)}")
            if not cur:
                break
            time.sleep(0.35)
        except Exception as e:
            print(f"batch {i} err {e}")
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

        soccer_pt=[]
        for m in markets:
            tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "2.5" not in tl and "3.5" not in tl:
                continue
            if "over" not in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl:
                continue
            if "both teams to score" in tl or "wins by more than" in tl:
                continue
            # Must have goals scored or point total
            if "goals scored" not in tl and "point total" not in tl and "total" not in tl:
                # Keep if team name present
                if "【entity-sassuolo¦canonical_name=Sassuolo】" not in tl and "【entity-fiorentina¦canonical_name=Fiorentina】" not in tl and "atalanta" not in tl and "【entity-newcastle¦canonical_name=newcastle】" not in tl and "【entity-everton¦canonical_name=everton】" not in tl and "cruz" not in tl:
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
            if "【entity-sassuolo¦canonical_name=Sassuolo】" in tl and "【entity-fiorentina¦canonical_name=Fiorentina】" in tl:
                team="SAS-FIO"
            elif "【entity-sassuolo¦canonical_name=Sassuolo】" in tl:
                team="SAS-FIO" if "【entity-fiorentina¦canonical_name=Fiorentina】" in tl or "fio" in tl else "SAS"
            elif "【entity-fiorentina¦canonical_name=Fiorentina】" in tl:
                team="SAS-FIO"
            elif "atalanta" in tl and "【entity-parma¦canonical_name=parma】" in tl:
                team="ATA-PAR"
            elif "atalanta" in tl:
                team="ATA-PAR"
            elif "【entity-parma¦canonical_name=parma】" in tl:
                team="ATA-PAR"
            elif "【entity-newcastle¦canonical_name=newcastle】" in tl and "【entity-everton¦canonical_name=everton】" in tl:
                team="NEW-EVE"
            elif "【entity-newcastle¦canonical_name=newcastle】" in tl:
                team="NEW-EVE"
            elif "【entity-everton¦canonical_name=everton】" in tl:
                team="NEW-EVE"
            elif "cruz" in tl:
                team="CZ"
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer_pt.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"exp_dt":exp_dt,"exp":exp_dt.strftime("%m-%d %H:%M"),"exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),"vol":m.get("volume",0) or 0,"real":real,"tl":tl[:120]})

        tomorrow_pt=[s for s in soccer_pt if tomorrow_start_utc <= s["exp_dt"] < tomorrow_end_utc]
        sas_fio=[s for s in soccer_pt if "SAS" in s["team"] or "FIO" in s["team"]]
        new_eve=[s for s in soccer_pt if "NEW" in s["team"] or "EVE" in s["team"]]

        print(f"V79 total {len(markets)} pt {len(soccer_pt)} tomorrow {len(tomorrow_pt)} SAS {len(sas_fio)} NEW {len(new_eve)}")

        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V79 16k Deep - Today PST {today_str} Tomorrow PST {tomorrow_str} - Total {len(markets)} PT {len(soccer_pt)} TomorrowPT {len(tomorrow_pt)} SAS-FIO {len(sas_fio)} NEW-EVE {len(new_eve)} - Screenshot 40% should be here")

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
                msg=f"TOMORROW PST {tomorrow_str} - {len(tomorrow_pt)} PT - {len(middles)} Middle - Screenshot FOUND!\n"
                for i,(a,b) in enumerate(middles,1):
                    tag="LIVE" if a["real"] else "EST"
                    msg+=f"{i}. {a['team']} [{tag}] {b['exp_pst']}\n   O2.5 {a['over']}c + U3.5 {b['under']}c (O3.5 {b['over']}c) Vol {b['vol']}\n"
                send(msg)
            else:
                msg=f"TOMORROW PST {tomorrow_str} - {len(tomorrow_pt)} PT - No middle, details:\n"
                for s in tomorrow_pt[:8]:
                    tag="LIVE" if s["real"] else "EST"
                    msg+=f"{s['team']} [{tag}] {s['clean']} {s['over']}c {s['exp_pst']} Vol {s['vol']}\n {s['tl'][:50]}\n"
                send(msg)
        else:
            # Still 0
            if soccer_pt:
                by_date={}
                for s in soccer_pt:
                    d=(s["exp_dt"]-timedelta(hours=7)).strftime("%m-%d")
                    if d not in by_date:
                        by_date[d]=[]
                    by_date[d].append(s)
                sd=sorted(by_date.keys())
                msg=f"TOMORROW PST {tomorrow_str} - 0 PT in 16k - SAS {len(sas_fio)} NEW {len(new_eve)} - Dates {sd[:5]}\n"
                for s in sas_fio[:3]:
                    msg+=f"SAS-FIO {s['clean']} {s['over']}c {s['exp_pst']} Vol {s['vol']}\n"
                send(msg)

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(2
