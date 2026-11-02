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

def get_all():
    all_m=[]
    cur=None
    for i in range(20):
        for retry in range(3):
            try:
                p={"status":"open","limit":400}
                if cur:
                    p["cursor"]=cur
                r=requests.get(f"{BASE}/markets", params=p, timeout=20)
                if r.status_code==429:
                    time.sleep(5)
                    continue
                if r.status_code!=200:
                    time.sleep(1)
                    continue
                data=r.json()
                ms=data.get("markets",[])
                if not ms:
                    return all_m
                all_m.extend(ms)
                cur=data.get("cursor")
                if not cur:
                    return all_m
                time.sleep(0.6)
                break
            except:
                time.sleep(1)
                continue
    return all_m

def analyze():
    try:
        markets=get_all()
        soccer=[]
        # PST Timezone Fix - LA Time
        utc_now=datetime.utcnow()
        pst_now=utc_now - timedelta(hours=7)  # PST UTC-7 (PDT UTC-7)
        # မနက်ဖြန် PST
        tomorrow_pst=pst_now + timedelta(days=1)
        tomorrow_start_pst=datetime(tomorrow_pst.year, tomorrow_pst.month, tomorrow_pst.day, 0, 0, 0)
        tomorrow_end_pst=tomorrow_start_pst + timedelta(days=1)
        # UTC နဲ့ ပြန်ပြောင်း filter လုပ်ဖို့
        tomorrow_start_utc=tomorrow_start_pst + timedelta(hours=7)
        tomorrow_end_utc=tomorrow_end_pst + timedelta(hours=7)
        tomorrow_str=tomorrow_start_pst.strftime("%Y-%m-%d")
        today_str_pst=pst_now.strftime("%Y-%m-%d")

        for m in markets:
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
            if "both teams to score" in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl:
                continue
            if "wins by more than" in tl:
                continue
            if "over" not in tl or "goals scored" not in tl:
                continue
            if "2.5" not in tl and "3.5" not in tl:
                continue
            exp=m.get("expiration_time","")
            if not exp:
                continue
            try:
                exp_dt=datetime.fromisoformat(exp.replace("Z",""))
                # မနက်ဖြန် PST ပွဲတွေပဲ
                if exp_dt < tomorrow_start_utc:
                    continue
                if exp_dt >= tomorrow_end_utc:
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

            txt=tl
            team=""
            if "newcastle" in txt and "everton" in txt:
                team="NEW-EVE"
            elif "newcastle" in txt:
                team="NEW"
            elif "everton" in txt:
                team="EVE"
            elif "cruz" in txt:
                team="CZ"
            elif "tijuana" in txt:
                team="TJ"
            elif "vancouver" in txt:
                team="VAN"
            elif "seattle" in txt:
                team="SEA"
            elif "nashville" in txt:
                team="NSH"
            elif "miami" in txt:
                team="MIA"
            elif "atalanta" in txt or "parma" in txt:
                team="ATA-PAR"
            elif "lorient" in txt or "brest" in txt:
                team="LOR-BRE"
            elif "sassuolo" in txt or "fiorentina" in txt:
                team="SAS-FIO"
            elif " vs " in txt:
                team="SOC"
            if not team:
                continue

            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"exp":exp_dt.strftime("%m-%d %H:%M"),"vol":m.get("volume",0) or 0})

        print(f"V73 PST total {len(markets)} soccer {len(soccer)} tomorrow PST {tomorrow_str} today PST {today_str_pst}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V73 PST Fix - Today PST {today_str_pst} Tomorrow PST {tomorrow_str} - Total {len(markets)} Soccer TOMORROW {len(soccer)} PST")

        if soccer:
            by_team={}
            for s in soccer:
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
                msg=f"TOMORROW PST {tomorrow_str} - {len(soccer)} games - {len(middles)} Middle\n\n"
                for i,(a,b) in enumerate(middles,1):
                    msg+=f"{i}. {a['team']} {b['exp']} PST\n   O2.5 {a['over']}c + U3.5 {b['under']}c\n   Vol {b['vol']} | 3=win\n\n"
                send(msg)
            else:
                msg=f"TOMORROW PST {tomorrow_str} - {len(soccer)} games - No middle\n\n"
                for s in sorted(soccer, key=lambda x: x["vol"], reverse=True)[:6]:
                    msg+=f"{s['team']} O2.5 {s['over']}c Exp {s['exp']} Vol {s['vol']}\n"
                send(msg)
        else:
            send(f"TOMORROW PST {tomorrow_str} - No games tomorrow PST - Today PST {today_str_pst} မှာ 8000 ထဲ မနက်ဖြန် ပွဲ မရှိဘူး")

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(2)
    send(f"V73 PST Fix starting - Tomorrow should be 11-02 PST")
    while True:
        try:
            analyze()
            time.sleep(200)
        except Exception as e:
            print(e)
            time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V73 PST running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
