import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500].replace(" Kalshi","KLSH")}, timeout=15)
    except:
        pass

def get_all():
    all_m=[]
    cur=None
    for i in range(20):
        try:
            p={"status":"open","limit":400}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=12)
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
            time.sleep(0.4)
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
                if "sassuolo" in tl and "fiorentina" in tl:
                    team="SAS-FIO"
                elif "sassuolo" in tl:
                    team="SAS-FIO"
                else:
                    team="SAS-FIO"
            elif "atalanta" in tl or "parma" in tl:
                team="ATA-PAR"
            elif "newcastle" in tl or "everton" in tl:
                team="NEW-EVE"
            elif "cruz" in tl:
                team="CZ"

            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer_pt.append({"over":ya,"clean":clean,"team":team,"exp_dt":exp_dt,"exp":exp_dt.strftime("%m-%d %H:%M"),"exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),"vol":m.get("volume",0) or 0,"real":real,"tl":tl[:100]})

        tomorrow_pt=[s for s in soccer_pt if tomorrow_start_utc <= s["exp_dt"] < tomorrow_end_utc]
        sas=[s for s in soccer_pt if "SAS" in s["team"]]
        new=[s for s in soccer_pt if "NEW" in s["team"]]

        print(f"V80 total {len(markets)} pt {len(soccer_pt)} tomorrow {len(tomorrow_pt)} SAS {len(sas)} NEW {len(new)}")

        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V80 Light 8k - Today PST {today_str} Tomorrow PST {tomorrow_str} - Total {len(markets)} PT {len(soccer_pt)} TomorrowPT {len(tomorrow_pt)} SAS-FIO {len(sas)} NEW-EVE {len(new)} - Broad filter")

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
                msg=f"TOMORROW PST {tomorrow_str} - {len(tomorrow_pt)} PT - {len(middles)} Middle - Screenshot!\n"
                for i,(a,b) in enumerate(middles,1):
                    tag="LIVE" if a["real"] else "EST"
                    msg+=f"{i}. {a['team']} [{tag}] {b['exp_pst']}\n   O2.5 {a['over']}c + U3.5 {b['under']}c (O3.5 {b['over']}c) Vol {b['vol']}\n"
                send(msg)
            else:
                msg=f"TOMORROW PST {tomorrow_str} - {len(tomorrow_pt)} PT - No middle\n"
                for s in tomorrow_pt[:6]:
                   
