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
    for i in range(15):
        try:
            p={"status":"open","limit":400}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=15)
            if r.status_code!=200:
                break
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

def get_ob_price(ticker):
    try:
        r=requests.get(f"{BASE}/markets/{ticker}/orderbook", timeout=8)
        if r.status_code!=200:
            return None
        data=r.json()
        ob=data.get("orderbook",{})
        for key in ["yes_dollars","yes","no_dollars","no"]:
            arr=ob.get(key,[])
            if arr:
                try:
                    best=arr[-1]
                    price=float(best[0]) if isinstance(best, (list,tuple)) else float(best)
                    if "no" in key:
                        price=1-price
                    return int(price*100)
                except:
                    continue
    except:
        pass
    return None

def team_name(m):
    txt=(m.get("yes_sub_title","")+" "+m.get("title","")+" "+m.get("event_ticker","")).lower()
    if "newcastle" in txt and "everton" in txt:
        return "NEW-EVE"
    if "newcastle" in txt:
        return "NEW"
    if "everton" in txt:
        return "EVE"
    if "lorient" in txt:
        return "LOR-BRE"
    if "sassuolo" in txt or "fiorentina" in txt:
        return "SAS-FIO"
    if "atalanta" in txt or "parma" in txt:
        return "ATA-PAR"
    if "cruz" in txt:
        return "CZ"
    if "tijuana" in txt:
        return "TJ"
    if "vancouver" in txt:
        return "VAN"
    if "seattle" in txt:
        return "SEA"
    if "nashville" in txt:
        return "NSH"
    if "miami" in txt:
        return "MIA"
    if "quilmes" in txt:
        return "QL"
    if "lanus" in txt:
        return "LN"
    if "palmeiras" in txt:
        return "PAL"
    if "gremio" in txt:
        return "GRE"
    if " vs " in txt:
        # Generic vs -> 3+3
        parts=txt.split(" vs ")
        if len(parts)>=2:
            a=parts[0].split()[-1]
            b=parts[1].split()[0]
            if len(a)>=2 and len(b)>=2:
                return (a[:3]+"-"+b[:3]).upper()
    return ""

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V64 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.utcnow()
        for m in markets:
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
            ya=None
            ya_raw=m.get("yes_ask")
            yb=m.get("yes_bid")
            lp=m.get("last_price")
            for v in [ya_raw, yb, lp]:
                if v not in [None,0,"0",""]:
                    try:
                        ya=int(float(v))
                        break
                    except:
                        continue
            vol=m.get("volume",0) or 0
            team=team_name(m)
            if not team or len(team)<2:
                continue
            if team.lower() in ["yes","no"]:
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            real= ya is not None
            soccer.append({"over":ya if ya is not None else 50,"under":100-(ya if ya is not None else 50),"clean":clean,"team":team,"ticker":m.get("ticker",""),"exp":exp_str[5:16] if exp_str else "","vol":vol,"real":real,"raw_ya":ya_raw,"raw_yb":yb})

        # Sort by volume to get top 20 for orderbook (NEW-EVE 2419 should be top)
        soccer_by_vol=sorted(soccer, key=lambda x: x["vol"], reverse=True)
        # Fetch orderbook only for top 20 with Vol 0 and no real price
        for s in soccer_by_vol[:20]:
            if not s["real"] and s["ticker"]:
                ob=get_ob_price(s["ticker"])
                if ob is not None and 5 <= ob <= 95:
                    s["over"]=ob
                    s["under"]=100-ob
                    s["real"]=True
                time.sleep(0.2)

        soccer.sort(key=lambda x: (x["real"], x["vol"]), reverse=True)
        print(f"total {len(markets)} soccer {len(soccer)} real {sum(1 for s in soccer if s['real'])}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            real_cnt=sum(1 for s in soccer if s["real"])
            top_vol=soccer_by_vol[0]["vol"] if soccer_by_vol else 0
            send(f"V64 FINAL Volume Top Orderbook - Total {len(markets)} Soccer {len(soccer)} (Real {real_cnt}) TopVol {top_vol} - NEW-EVE 55% Vol 2419 catch via orderbook")

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
                    a=max(o25, key=lambda x: (x["real"], x["vol"]))
                    b=max(o35, key=lambda x: (x["real"], x["vol"]))
                    middles.append((a,b))

            middles=sorted(middles, key=lambda x: (x[0]["real"], x[0]["vol"]), reverse=True)[:6]
            if middles:
                msg=f"MIDDLE {now} - {len(soccer)} games - {len(middles)} Middle Vol Top OB\n\n"
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
    send("V64 starting vol top orderbook NEW-EVE 55%")
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
        self.wfile.write(b"V64 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
