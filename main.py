import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        # Avoid banned words that trigger entity tag
        safe=msg.replace("Kalshi","KLSH").replace("kalshi","KLSH")
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":safe}, timeout=15)
    except:
        pass

def analyze():
    try:
        all_m=[]
        cur=None
        for i in range(12):
            try:
                p={"status":"open","limit":400}
                if cur:
                    p["cursor"]=cur
                r=requests.get(f"{BASE}/markets", params=p, timeout=12)
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
                time.sleep(0.3)
            except:
                break

        soccer=[]
        now_utc=datetime.utcnow()
        for m in all_m:
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
            if exp:
                try:
                    if datetime.fromisoformat(exp.replace("Z","")) < now_utc:
                        continue
                except:
                    pass
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
            if not (5 <= ya <= 95):
                continue
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
            elif "lorient" in txt:
                team="LOR-BRE"
            elif "sassuolo" in txt or "fiorentina" in txt:
                team="SAS-FIO"
            elif " vs " in txt:
                team="SOC"
            if not team:
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"exp":exp[5:16] if exp else "","vol":m.get("volume",0) or 0})

        print(f"V68 total {len(all_m)} soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V68 FINAL Clean Deploy - Total {len(all_m)} Soccer {len(soccer)} - Tag fixed, 12 batch, Middle OK")

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

            middles=middles[:5]
            if middles:
                msg=f"MIDDLE {time.strftime('%H:%M:%S')} - {len(soccer)} games - {len(middles)} Middle Clean No Tag\n\n"
                for i,(a,b) in enumerate(middles,1):
                    msg+=f"{i}. {a['team']} [EST]\n   O2.5 {a['over']}c + U3.5 {b['under']}c (O3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n   3 = both win | PRE 2 side | 15' U add | 70' JACKPOT O\n\n"
                send(msg)
            else:
                top=soccer[:5]
                if top:
                    msg=f"TOP {time.strftime('%H:%M:%S')} - {len(soccer)} games\n\n"
                    for s in top:
                        msg+=f"{s['team']} O2.5 {s['over']}c Vol {s['vol']} Exp {s['exp']}\n"
                    send(msg)

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(2)
    send(f"V68 starting - PORT {PORT} - Clean logic no tag")
    while True:
        try:
            analyze()
            time.sleep(180)
        except Exception as e:
            print(e)
            time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V68 running clean")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
