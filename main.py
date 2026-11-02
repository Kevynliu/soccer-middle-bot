import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        safe=msg.replace(" Kalshi","KLSH")
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
        now_utc=datetime.utcnow()
        # မနက်ဖြန် date range
        tomorrow=now_utc + timedelta(days=1)
        tomorrow_start=datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
        tomorrow_end=tomorrow_start + timedelta(days=1)
        # ဥပမာ ဒီနေ့ 11-04 ဆို မနက်ဖြန် 11-05 00:00 - 23:59 ပွဲတွေပဲ
        tomorrow_str=tomorrow_start.strftime("%Y-%m-%d")

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
                # မနက်ဖြန်မှ ကန်မယ့် ပွဲတွေပဲ - ဒီနေ့ပြီးသွားတာ နဲ့ ဟိုး အဝေးကြီး skip
                if exp_dt < tomorrow_start:
                    continue  # ဒီနေ့ ပွဲ skip
                if exp_dt >= tomorrow_end:
                    continue  # သဘက်ခါ နဲ့ အဝေးကြီး ပွဲ skip
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
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"exp":exp_dt.strftime("%H:%M"),"vol":m.get("volume",0) or 0,"exp_full":exp_dt})

        print(f"V72 TOMORROW total {len(markets)} soccer {len(soccer)} tomorrow {tomorrow_str}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V72 TOMORROW ONLY - {tomorrow_str} - Total {len(markets)} Soccer TOMORROW {len(soccer)} - မနက်ဖြန် ပွဲတွေပဲ")

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
                msg=f"TOMORROW {tomorrow_str} - {len(soccer)} games TOMORROW - {len(middles)} Middle\n\n"
                for i,(a,b) in enumerate(middles,1):
                    msg+=f"{i}. {a['team']} TOMORROW {b['exp']}\n   O2.5 {a['over']}c + U3.5 {b['under']}c\n   Vol {b['vol']} | 3 = both win | PRE 2 side\n\n"
                send(msg)
            else:
                if soccer:
                    msg=f"TOMORROW {tomorrow_str} - {len(soccer)} games TOMORROW - No middle\n\n"
                    for s in sorted(soccer, key=lambda x: x["vol"], reverse=True)[:6]:
                        msg+=f"{s['team']} O2.5 {s['over']}c Exp {s['exp']} Vol {s['vol']}\n"
                    send(msg)
                else:
                    send(f"TOMORROW {tomorrow_str} - No games TOMORROW - ဒီနေ့ 8000 ထဲ မနက်ဖြန် ပွဲ မရှိဘူး")
        else:
            send(f"TOMORROW {tomorrow_str} - No soccer TOMORROW - မနက်ဖြန် ပွဲ မရှိဘူး, သဘက်ခါ ပွဲတွေပဲ ရှိတယ်")

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(2)
    send(f"V72 TOMORROW ONLY starting - မနက်ဖြန် ပွဲတွေပဲ")
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
        self.wfile.write(b"V72 TOMORROW running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
