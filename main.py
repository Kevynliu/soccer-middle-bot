import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
ODDS=os.getenv("ODDS_API_KEY","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"
ODDS_BASE="https://api.the-odds-api.com/v4"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=20)
    except:
        pass

def get_kalshi():
    all_m=[]
    cur=None
    for i in range(12):
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
            time.sleep(0.5)
        except:
            break
    return all_m

def get_odds_leagues():
    leagues=[]
    if not ODDS:
        return leagues
    # EPL, 【entity-Serie A¦canonical_name=Serie A】, Ligue 1, La Liga, Bundesliga tomorrow
    sports=["soccer_epl","soccer_italy_serie_a","soccer_france_ligue_one","soccer_spain_la_liga","soccer_germany_bundesliga"]
    for sport in sports:
        try:
            url=f"{ODDS_BASE}/sports/{sport}/odds"
            params={"apiKey":ODDS,"regions":"us,uk,eu","markets":"totals","oddsFormat":"decimal","dateFormat":"iso"}
            r=requests.get(url, params=params, timeout=15)
            if r.status_code!=200:
                continue
            data=r.json()
            for g in data[:10]: # top 10
                home=g.get("home_team","")
                away=g.get("away_team","")
                commence=g.get("commence_time","")
                # Find Over 2.5
                totals=[]
                for bk in g.get("bookmakers",[]):
                    for mk in bk.get("markets",[]):
                        if mk.get("key")=="totals":
                            for o in mk.get("outcomes",[]):
                                if o.get("name")=="Over" and o.get("point") in [2.5,3.5]:
                                    totals.append((o.get("point"),o.get("price")))
                if totals:
                    leagues.append({"league":sport.replace("soccer_","").upper(),"match":f"{home} vs {away}","time":commence[5:16] if commence else "","totals":totals})
            time.sleep(0.5)
        except:
            continue
    return leagues

def team_name_kalshi(m):
    y=(m.get("yes_sub_title","") or "").lower()
    t=(m.get("title","") or "").lower()
    raw=y+" "+t
    if "cruz" in raw:
        return "CruzAzul"
    if "tijuana" in raw:
        return "Tijuana"
    if "quilmes" in raw:
        return "Quilmes"
    if "lanus" in raw:
        return "Lanus"
    if "vancouver" in raw:
        return "Vancouver"
    if "seattle" in raw:
        return "Seattle"
    if "nashville" in raw:
        return "Nashville"
    if "palmeiras" in raw:
        return "Palmeiras"
    if "gremio" in raw:
        return "Gremio"
    if "los angeles" in raw and "miami" in raw:
        return "LAFCvsMIA"
    if "miami" in raw:
        return "MiamiTeam"
    return ""

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V57 {now}")
    try:
        # Kalshi part - existing
        markets=get_kalshi()
        soccer=[]
        now_utc=datetime.utcnow()
        for m in markets:
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
            if "both teams to score" in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl or "lendeborg" in tl or "austin reaves" in tl or "yaxel" in tl:
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
            for k in ["yes_ask","yes_bid","last_price"]:
                v=m.get(k)
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
            team=team_name_kalshi(m)
            if not team:
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            soccer.append({"over":ya,"clean":clean,"team":team,"exp":exp_str[5:16] if exp_str else "","vol":m.get("volume",0)})

        print(f"total {len(markets)} soccer {len(soccer)}")
        # Odds API part - tomorrow EPL etc
        odds_leagues=get_odds_leagues()
        print(f"odds leagues {len(odds_leagues)}")

        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V57 FINAL EPL+SerieA Live - 【entity-Kalshi¦canonical_name=Kalshi】 {len(soccer)} + OddsAPI {len(odds_leagues)} leagues - Tomorrow EPL included")

        # Middle from Kalshi
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
                    middles.append((o25[0],o35[0]))
            middles=middles[:4]
            if middles:
                msg=f"PRE-MATCH MIDDLE {now} - Kalshi {len(soccer)} Soccer - {len(middles)} Middle\n\n"
                for i,(a,b) in enumerate(middles,1):
                    msg+=f"{i}. {a['team']}\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c\n   Exp {b['exp']} Vol {b['vol']}\n   3 goals = both win | PRE 2 side | 15' Under | 70' Jackpot\n\n"
                send(msg)

        # Tomorrow EPL etc from Odds API
        if odds_leagues:
            msg=f"TOMORROW EPL/【entity-SERIE A¦canonical_name=Serie A】/LIGUE 1 {now} - {len(odds_leagues)} matches - 【entity-Kalshi¦canonical_name=Kalshi】 doesn't have, OddsAPI has\n\n"
            for i,g in enumerate(odds_leagues[:6],1):
                tot_str=", ".join([f"Over {p} @ {price}" for p,price in g["totals"][:2]])
                msg+=f"{i}. [{g['league']}] {g['match']}\n   {tot_str}\n   Time {g['time']} - 3 goals Middle if Over 2.5 + Under 3.5\n\n"
            msg+="【entity-Kalshi¦canonical_name=Kalshi】 has only MLS/LigaMX, so EPL middle = use 【entity-DraftKings¦canonical_name=DraftKings】 + 【entity-Kalshi¦canonical_name=Kalshi】 Under 3.5 or wait 【entity-Kalshi¦canonical_name=Kalshi】 open\n"
            send(msg)

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(3)
    send("V57 starting EPL+【entity-Kalshi¦canonical_name=Kalshi】")
    while True:
        try:
            analyze()
            time.sleep(300)
        except Exception as e:
            print(e)
            time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V57 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
