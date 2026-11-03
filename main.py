import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500].replace(" 【entity-Kalshi¦canonical_name=Kalshi】"," KLSH")}, timeout=12)
    except:
        pass

def get_markets(total=5000):
    all_ms=[]
    cursor=None
    while len(all_ms) < total:
        try:
            p={"status":"open","limit":250}
            if cursor: p["cursor"]=cursor
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code==429:
                time.sleep(60)
                continue
            if r.status_code!=200:
                break
            d=r.json()
            batch=d.get("markets",[])
            all_ms.extend(batch)
            cursor=d.get("cursor")
            if not cursor or not batch:
                break
            time.sleep(0.4)
        except:
            break
    return all_ms

def analyze():
    ms=get_markets(total=5000)
    if not ms:
        return
    utc_now=datetime.utcnow()
    
    games={}  # team_key -> {o25: [], o35: []}
    for m in ms:
        tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
        if "goals scored" not in tl: continue
        if "2.5" not in tl and "3.5" not in tl: continue
        if "over" not in tl: continue
        if "edmonton" in tl or "ottawa" in tl or "both teams" in tl: continue
        exp=m.get("expiration_time","")
        try:
            exp_dt=datetime.fromisoformat(exp.replace("Z","")) if exp else None
            if not exp_dt or exp_dt < utc_now: continue
        except:
            continue
        
        # Price
        ya=None
        real=False
        for v in [m.get("yes_ask"), m.get("yes_bid"), m.get("last_price")]:
            if v not in [None,0,""]:
                try:
                    ya=int(float(v))
                    if ya>0:
                        real=True
                        break
                except:
                    continue
        if ya is None or ya==0: continue
        if ya<5 or ya>95: continue  # skip extreme
        
        # Team key - use ticker prefix to group same game
        ticker=m.get("ticker","")
        # Extract event id: KXSOCCER... -> group by first 2 teams
        team_key=ticker.split("-")[0][:30] if "-" in ticker else tl[:40]
        
        # Better grouping: by expiration + league
        exp_key=exp_dt.strftime("%m-%d %H")
        # Use title without over/under for grouping
        base_title=m.get("title","").lower().replace("over 2.5","").replace("over 3.5","").replace("goals scored","").strip()[:50]
        group_key=f"{base_title}|{exp_key}"
        
        if group_key not in games:
            games[group_key]= {"o25":[], "o35":[], "title":m.get("title",""), "exp_dt":exp_dt, "exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST")}
        
        entry={"over":ya,"under":100-ya,"real":real,"vol":m.get("volume",0) or 0,"ticker":ticker,"exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST")}
        if "2.5" in tl:
            games[group_key]["o25"].append(entry)
        else:
            games[group_key]["o35"].append(entry)

    # Find middles
    middles=[]
    for key,g in games.items():
        if g["o25"] and g["o35"]:
            # Best prices - lowest over = cheapest middle
            best_o25=min(g["o25"], key=lambda x: x["over"])  # Cheapest Over 2.5
            best_o35=min(g["o35"], key=lambda x: x["over"])  # Cheapest Over 3.5 = Under 3.5 cheapest when we buy Under
            # Middle: Buy Over 2.5 + Buy Under 3.5 (Under 3.5 = 100 - Over 3.5)
            # Cost = o25.over + (100 - o35.over) = o25.over + o35.under
            # If 3 goals: O2.5 wins (100) + U3.5 wins (100) = 200 - cost = profit
            # If 0-2 goals: U3.5 wins only
            # If 4+ goals: O2.5 wins only
            cost=best_o25["over"] + best_o35["under"]
            profit_3goals=200 - cost  # Both win
            loss_other=100 - cost  # One wins
            
            # Only good middles: cost < 100 = guaranteed profit? Actually cost <100 = arb, cost 100-110 = small risk middle
            if cost <= 110:  # Pay 100c get 100c back min, max 200 if exactly 3
                middles.append({
                    "key":key, "title":g["title"], "exp_pst":g["exp_pst"],
                    "o25":best_o25, "o35":best_o35,
                    "cost":cost, "profit_3":profit_3goals, "loss":loss_other
                })

    # Sort by profit
    middles=sorted(middles, key=lambda x: (-x["profit_3"], x["cost"]))[:8]

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"V93 REAL TRADER - Deploy OK!\nScanned {len(ms)} markets -> {len(games)} soccer games\nFound {len(middles)} middle opportunities (cost <=110)\nWill alert only when middle found - No more 0 PT spam!")

    if middles:
        msg=f"🔥 {len(middles)} MIDDLE FOUND! (3 goals = both win) 🔥\nTotal games scanned: {len(games)}\n\n"
        for i,m in enumerate(middles,1):
            tag_o="LIVE" if m["o25"]["real"] else "EST"
            tag_u="LIVE" if m["o35"]["real"] else "EST"
            # Clean title
            clean_title=m["title"][:50]
            msg+=f"{i}. {clean_title}\n"
            msg+=f"   O2.5 {m['o25']['over']}c [{tag_o}] + U3.5 {m['o35']['under']}c [{tag_u}] (O3.5 {m['o35']['over']}c)\n"
            msg+=f"   Cost {m['cost']}c -> If 3 goals = +{m['profit_3']}c profit, Else {m['loss']}c (Vol {m['o25']['vol']}/{m['o35']['vol']}) {m['exp_pst']}\n\n"
        send(msg)
    else:
        # Don't spam when no middle - only log
        print(f"No middle in {len(ms)} markets - {len(games)} games")
        # Send once per 6 hours if no middle
        if not hasattr(analyze,"last_no_middle") or time.time()-analyze.last_no_middle > 21600:
            analyze.last_no_middle=time.time()
            send(f"No middle (cost <=110) in {len(ms)} markets - {len(games)} games checked - Next check 5min")

def bot_loop():
    time.sleep(5)
    send(f"V93 REAL TRADER starting - No spam, only real middles - Deploy OK if you see this!")
    while True:
        try:
            analyze()
            time.sleep(300)
        except Exception as e:
            print(f"err {e}")
            time.sleep(300)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V93 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
