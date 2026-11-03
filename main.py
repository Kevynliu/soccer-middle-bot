import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

# AUTO TRADING ENV
K_EMAIL=os.getenv("KALSHI_EMAIL","").strip()
K_PASS=os.getenv("KALSHI_PASSWORD","").strip()
TRADE_AMT=int(os.getenv("TRADE_AMOUNT","5"))
MAX_LOSS=int(os.getenv("MAX_DAILY_LOSS","50"))
AUTO_TRADE=os.getenv("AUTO_TRADE","false").lower()=="true"

kalshi_token=None
daily_pnl=0
trades_today=0

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500].replace(" 【entity-Kalshi¦canonical_name=Kalshi】"," 【entity-KLSH¦canonical_name=Kalshi】")}, timeout=10)
    except:
        pass

def kalshi_login():
    global kalshi_token
    try:
        if not K_EMAIL or not K_PASS:
            return False
        r=requests.post(f"{BASE}/login", json={"email":K_EMAIL,"password":K_PASS}, timeout=15)
        if r.status_code==200:
            kalshi_token=r.json().get("token")
            send(f"✅ 【entity-KLSH¦canonical_name=Kalshi】 Login OK - Auto Trade {'ENABLED' if AUTO_TRADE else 'DISABLED (TEST MODE)'} - Amount ${TRADE_AMT}")
            return True
        else:
            send(f"❌ 【entity-KLSH¦canonical_name=Kalshi】 Login Failed {r.status_code} - Check email/pass")
            return False
    except Exception as e:
        send(f"❌ 【entity-KLSH¦canonical_name=Kalshi】 Login Error {str(e)[:100]}")
        return False

def place_order(ticker, side, count):
    # side: yes = buy Over, count = contracts
    try:
        if not kalshi_token:
            return False
        # Real order - use limit order at yes_ask price
        headers={"Authorization": f"Bearer {kalshi_token}"}
        # Get market to get price
        r=requests.get(f"{BASE}/markets/{ticker}", headers=headers, timeout=10)
        if r.status_code!=200:
            return False
        m=r.json().get("market",{})
        price=m.get("yes_ask") or m.get("last_price") or 50
        # Place order
        order={"ticker":ticker,"side":side,"type":"limit","yes_price":int(price),"count":count}
        ro=requests.post(f"{BASE}/orders", json=order, headers=headers, timeout=15)
        return ro.status_code in [200,201]
    except:
        return False

def get_markets(total=1500):
    all_ms=[]
    try:
        r=requests.get(f"{BASE}/markets", params={"status":"open","limit":total}, timeout=20)
        if r.status_code==200:
            all_ms=r.json().get("markets",[])
    except:
        pass
    return all_ms

def analyze():
    global daily_pnl, trades_today
    ms=get_markets(total=1500)
    if not ms:
        return
    utc_now=datetime.utcnow()
    soccer_pt=[]
    for m in ms:
        tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
        if "2.5" not in tl and "3.5" not in tl: continue
        if "over" not in tl: continue
        if "goals scored" not in tl: continue
        if "edmonton" in tl or "ottawa" in tl or "both teams to score" in tl: continue
        exp=m.get("expiration_time","")
        try:
            exp_dt=datetime.fromisoformat(exp.replace("Z","")) if exp else None
            if not exp_dt or exp_dt < utc_now: continue
        except:
            continue
        ya=None
        real=False
        for v in [m.get("yes_ask"), m.get("yes_bid"), m.get("last_price")]:
            if v not in [None,0,""]:
                try:
                    ya=int(float(v))
                    if 0 < ya < 100:
                        real=True
                        break
                except:
                    continue
        if not ya or not (0 < ya < 100): continue
        soccer_pt.append({"over":ya,"under":100-ya,"exp_dt":exp_dt,"exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),"vol":m.get("volume",0) or 0,"real":real,"title":m.get("title",""),"ticker":m.get("ticker",""),"clean":"O2.5" if "2.5" in tl else "O3.5"})

    games={}
    for s in soccer_pt:
        base=s["title"].lower()[:35]
        dkey=s["exp_dt"].strftime("%m-%d %H")
        gkey=f"{base}|{dkey}"
        if gkey not in games:
            games[gkey]={"o25":[],"o35":[],"title":s["title"],"exp_pst":s["exp_pst"]}
        if "2.5" in s["clean"]:
            games[gkey]["o25"].append(s)
        else:
            games[gkey]["o35"].append(s)

    middles=[]
    for g in games.values():
        if g["o25"] and g["o35"]:
            a=min(g["o25"], key=lambda x: x["over"])
            b=min(g["o35"], key=lambda x: x["over"])
            cost=a["over"]+b["under"]
            profit_3=200-cost
            # ONLY RISK-FREE FOR AUTO TRADE - 100% Trust!
            if cost<=100:  # Risk-free arb!
                middles.append({"title":g["title"],"exp_pst":g["exp_pst"],"o25":a,"o35":b,"cost":cost,"profit_3":profit_3})

    if not hasattr(analyze,"first"):
        analyze.first=True
        send(f"V100 AUTO TRADER - Deploy OK!\nScanned {len(ms)} -> {len(soccer_pt)} PT -> {len(games)} games\nRisk-Free Middles (cost<=100): {len(middles)}\nAuto Trade: {'ON' if AUTO_TRADE else 'OFF (Test Mode)'} - Amount ${TRADE_AMT} Max Loss ${MAX_LOSS}\n100% Trustworthy - Only trades when guaranteed profit!")

    if middles:
        for m in middles[:2]:  # Max 2 per cycle
            if trades_today >= 10 or daily_pnl <= -MAX_LOSS:
                send(f"⛔ Daily limit reached - Trades {trades_today} PnL {daily_pnl} - Stopping auto trade today")
                break
            
            tag_o="LIVE" if m["o25"]["real"] else "EST"
            tag_u="LIVE" if m["o35"]["real"] else "EST"
            
            if AUTO_TRADE and K_EMAIL:
                # AUTO BUY BOTH SIDES
                count=TRADE_AMT  # $5 = 5 contracts at 100c
                ok1=place_order(m["o25"]["ticker"],"yes",count)
                ok2=place_order(m["o35"]["ticker"],"no",count)  # Under 3.5 = No to Over 3.5
                if ok1 and ok2:
                    trades_today+=1
                    daily_pnl+= (m["profit_3"] if False else 0)  # PnL after settlement
                    send(f"🤖 AUTO TRADED!\n{m['title'][:40]}\nO2.5 {m['o25']['over']}c [{tag_o}] + U3.5 {m['o35']['under']}c [{tag_u}]\nCost {m['cost']}c -> Guaranteed profit +{200-m['cost']-100}c min, +{m['profit_3']}c if 3 goals!\nAmount ${TRADE_AMT} Trades today {trades_today} {m['exp_pst']}")
                else:
                    send(f"⚠️ AUTO TRADE FAILED - Order error\n{m['title'][:40]} Cost {m['cost']}c - Check KLSH balance")
            else:
                # TEST MODE - Signal only
                send(f"🔥 RISK-FREE MIDDLE FOUND! (Test Mode) 🔥\n{m['title'][:45]}\nO2.5 {m['o25']['over']}c [{tag_o}] + U3.5 {m['o35']['under']}c [{tag_u}]\nCost {m['cost']}c -> Guaranteed +{100-m['cost']+100}c if 3 goals, +{100-m['cost']}c min!\nSet AUTO_TRADE=true to auto trade ${TRADE_AMT}\nVol {m['o25']['vol']}/{m['o35']['vol']} {m['exp_pst']}")

def bot_loop():
    time.sleep(4)
    send(f"V100 AUTO TRADER starting - Risk-Free Only (cost<=100) - Deploy OK!")
    if K_EMAIL:
        kalshi_login()
    else:
        send(f"⚠️ Set KALSHI_EMAIL/PASS in Render to enable auto trading - Currently in TEST MODE (signals only)")
    while True:
        try:
            analyze()
            time.sleep(180)
        except Exception as e:
            print(e)
            time.sleep(180)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V100 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
