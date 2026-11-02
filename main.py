import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=20)
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
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code!=200:
                continue
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

def get_orderbook_price(ticker):
    try:
        r=requests.get(f"{BASE}/markets/{ticker}/orderbook", timeout=10)
        if r.status_code!=200:
            return None
        data=r.json()
        ob=data.get("orderbook",{})
        yes=ob.get("yes_dollars",[]) or ob.get("yes",[])
        no=ob.get("no_dollars",[]) or ob.get("no",[])
        # yes_dollars is [[price_dollars, count],...] price like "0.55"
        if yes:
            try:
                best=yes[-1]
                price=float(best[0]) if isinstance(best, (list,tuple)) else float(best)
                return int(price*100)
            except:
                pass
        if no:
            try:
                best=no[-1]
                price=float(best[0]) if isinstance(best, (list,tuple)) else float(best)
                # No bid 0.45 => Yes ask 55
                return int((1-price)*100)
            except:
                pass
    except:
        pass
    return None

def team_name(m):
    for field in [m.get("yes_sub_title",""), m.get("title",""), m.get("subtitle",""), m.get("event_ticker","")]:
        low=field.lower()
        if "newcastle" in low and "everton" in low:
            return "NEW-EVE"
        if "newcastle" in low:
            return "NEW"
        if "everton" in low:
            return "EVE"
        if "lorient" in low:
            return "LOR-BRE"
        if "sassuolo" in low or "fiorentina" in low:
            return "SAS-FIO"
        if "atalanta" in low or "parma" in low:
            return "ATA-PAR"
        if "cruz" in low:
            return "CZ"
        if "tijuana" in low:
            return "TJ"
        if "quilmes" in low:
            return "QL"
        if "lanus" in low:
            return "LN"
        if "vancouver" in low:
            return "VAN"
        if "seattle" in low:
            return "SEA"
        if "nashville" in low:
            return "NSH"
        if "miami" in low:
            return "MIA"
    return ""

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V62 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.utcnow()
        for m in markets:
            ticker=m.get("ticker","")
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
            if "both teams to score" in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl or "leon" in tl:
                continue
            if "wins by more than" in tl:
                continue
            if "over" not in tl or "goals scored" not in tl:
                continue
            if "2.5" not in tl and "3.5" not in tl:
                continue
            exp_str=m.get("expiration_time","")
            if exp_str:
                try:
                    exp_dt=datetime.fromisoformat(exp_str.replace("Z",""))
                    if exp_dt < now_utc:
                        continue
                except:
                    pass
            # Get price: first from market, then orderbook
            ya=None
            ya_raw=m.get("yes_ask")
            yb=m.get("yes_bid")
            lp=m.get("last_price")
            if ya_raw not in [None,0,"0",""]:
                try:
                    ya=int(float(ya_raw))
                except:
                    pass
            if ya is None and yb not in [None,0,"0",""]:
                try:
                    ya=int(float(yb))
                except:
                    pass
            if ya is None and lp not in [None,0,"0",""]:
                try:
                    ya=int(float(lp))
                except:
                    pass
            # If still None, try orderbook (for NEW-EVE 55%)
            real_from_ob=False
            if ya is None and ticker:
                ob_price=get_orderbook_price(ticker)
                if ob_price is not None and 5 <= ob_price <= 95:
                    ya=ob_price
                    real_from_ob=True
            if ya is None:
                ya=50
            if not (5 <= ya <= 95):
                continue
            team=team_name(m)
            if not team:
                continue
            if len(team) <2:
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            real= (ya_raw is not None and ya_raw!=0) or (yb is not None and yb!=0) or real_from_ob
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ticker":ticker,"exp":exp_str[5:16] if exp_str else "","vol":m.get("volume",0) or 0,"real":real})

        soccer.sort(key=lambda x: (x["real"], x["vol"]), reverse=True)
        print(f"total {len(markets)} soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            real_cnt=sum(1 for s in soccer if s["real"])
            send(f"V62 FINAL Orderbook - Total {len(markets)} Soccer {len(soccer)} (Real {real_cnt}) - NEW-EVE 55% should be LIVE")

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
                    a=min(o25, key=lambda x: x["over"])
                    b=min(o35, key=lambda x: x["over"])
                    middles.append((a,b))

            middles=sorted(middles, key=lambda x: x[0]["vol"], reverse=True)[:6]
            if middles:
                msg=f"MIDDLE {now} - {len(soccer)} games - {len(middles)} Middle EPL Real\n\n"
                for i,(a,b) in enumerate(middles,1):
                    tag="LIVE" if a["real"] or b["real"] else "EST"
                    msg+=f"{i}. {a['team']} [{tag}]\n   O2.5 {a['over']}c + U3.5 {b['under']}c (O3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n   3 = both win | PRE 2 side | 15' U add | 70' JACKPOT O\n\n"
                send(msg)
            else:
                top=sorted([s for s in soccer if "2.5" in s["clean"]], key=lambda x: (x["real"], x["vol"]), reverse=True)[:6]
                if top:
                    msg=f"TOP O2.5 {now} - {len(soccer)} games Real {sum(1 for s in soccer if s['real'])}\n\n"
                    for s in top:
                        tag="LIVE" if s["real"] else "EST"
                        msg+=f"{s['team']} [{tag}] O2.5 {s['over']}c Vol {s['vol']} Exp {s['exp']}\n"
                    send(msg)

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(3)
    send("V62 starting orderbook for NEW-EVE 55%")
    while True:
        try:
            analyze()
            time.sleep(240)
        except Exception as e:
            print(e)
            time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V62 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
