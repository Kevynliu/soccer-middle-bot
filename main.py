import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

# === ENV ===
BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        # Kalshi စာလုံးပါရင် Entity Tag ဖြစ်လို့ KLSH လို့ပြောင်း
        txt=msg[:3500].replace("Kalshi","KLSH")
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":txt}, timeout=15)
    except Exception as e:
        print(f"send err {e}")

def get_markets_safe(limit=1000):
    """429 မထိအောင် safe call - 1 ခါပဲခေါ်မယ်"""
    try:
        r=requests.get(f"{BASE}/markets", params={"status":"open","limit":limit}, timeout=20)
        if r.status_code==429:
            print("429 hit - waiting 60s")
            time.sleep(60)
            r=requests.get(f"{BASE}/markets", params={"status":"open","limit":limit}, timeout=20)
            if r.status_code==429:
                send("V90 Still 429 - Kalshi blocked 10 min - waiting 10 min")
                return None
        if r.status_code!=200:
            print(f"API {r.status_code}")
            return []
        return r.json().get("markets",[])
    except Exception as e:
        print(f"net err {e}")
        return []

def analyze():
    ms=get_markets_safe(limit=1000)  # 1000 = Deploy OK limit, 4000+ Fail
    if ms is None:
        return # 429 wait
    if not ms:
        return

    utc_now=datetime.utcnow()
    pst_now=utc_now - timedelta(hours=7)  # La Puente CA PST
    tomorrow_pst=pst_now + timedelta(days=1)
    tomorrow_start_pst=datetime(tomorrow_pst.year, tomorrow_pst.month, tomorrow_pst.day, 0,0,0)
    tomorrow_end_pst=tomorrow_start_pst + timedelta(days=1)
    tomorrow_start_utc=tomorrow_start_pst + timedelta(hours=7)
    tomorrow_end_utc=tomorrow_end_pst + timedelta(hours=7)
    tomorrow_str=tomorrow_start_pst.strftime("%m-%d PST")
    today_str=pst_now.strftime("%m-%d PST")

    soccer_pt=[]
    for m in ms:
        tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
        full=(m.get("title","")+" "+m.get("subtitle","")).lower()

        # === SOCCER ONLY FILTER - အမှန်ဆုံး ===
        # 1. Over 2.5 / 3.5 ပါရမယ်
        if "2.5" not in tl and "3.5" not in tl:
            continue
        # 2. over ပါရမယ်
        if "over" not in tl:
            continue
        # 3. goals scored ပါမှ Soccer - NBA wins by over 11.5 point filter out
        if "goals scored" not in tl:
            continue
        # 4. Junk filter
        if "edmonton" in tl or "ottawa" in tl or "both teams to score" in tl or "wins by more than" in tl or "wins by over" in full:
            continue
        # 5. Finished filter
        exp=m.get("expiration_time","")
        try:
            exp_dt=datetime.fromisoformat(exp.replace("Z","")) if exp else None
            if not exp_dt or exp_dt < utc_now:
                continue
        except:
            continue

        # Real price - yes_ask
        ya=None
        real=False
        for v in [m.get("yes_ask"), m.get("yes_bid"), m.get("last_price")]:
            if v not in [None,0,"0",""]:
                try:
                    ya=int(float(v))
                    if ya>0:
                        real=True
                        break
                except:
                    continue
        if ya is None:
            ya=50

        # Team name clean - short code to avoid entity tag
        team="SOC"
        if "sassuolo" in tl and "fiorentina" in tl: team="SAS-FIO"
        elif "sassuolo" in tl: team="SAS"
        elif "fiorentina" in tl: team="FIO"
        elif "newcastle" in tl and "everton" in tl: team="NEW-EVE"
        elif "newcastle" in tl: team="NEW"
        elif "everton" in tl: team="EVE"
        elif "atalanta" in tl: team="ATA"
        elif "parma" in tl: team="PAR"
        elif "cruz azul" in tl: team="CZ"
        elif "inter miami" in tl or "miami" in tl: team="MIA"
        elif "lorient" in tl: team="LOR"
        elif "brest" in tl: team="BRE"

        clean="Over 2.5" if "2.5" in tl else "Over 3.5"
        under=100-ya

        soccer_pt.append({
            "team":team, "clean":clean, "over":ya, "under":under,
            "exp_dt":exp_dt, "exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),
            "vol":m.get("volume",0) or 0, "real":real, "ticker":m.get("ticker","")
        })

    # Tomorrow filter
    tomorrow_pt=[s for s in soccer_pt if tomorrow_start_utc <= s["exp_dt"] < tomorrow_end_utc]
    today_pt=[s for s in soccer_pt if pst_now.replace(hour=0,minute=0,second=0,microsecond=0) + timedelta(hours=7) <= s["exp_dt"] < tomorrow_start_utc]

    # === First run message ===
    if not hasattr(analyze,"first"):
        analyze.first=True
        # Count by date
        by_date={}
        for s in soccer_pt:
            d=(s["exp_dt"]-timedelta(hours=7)).strftime("%m-%d")
            by_date[d]=by_date.get(d,0)+1
        sd=sorted(by_date.items())
        send(f"V90 FINAL PERFECT - Deploy OK!\nToday {today_str} {len(today_pt)} games\nTomorrow {tomorrow_str} {len(tomorrow_pt)} PT games\nTotal {len(ms)} markets -> Soccer PT {len(soccer_pt)} (NBA filtered)\nDates: {sd[:5]}\n5min cooldown active - No 429")

    # === Tomorrow report ===
    if tomorrow_pt:
        by_team={}
        for s in tomorrow_pt:
            by_team.setdefault(s["team"], []).append(s)
        
        middles=[]
        msg=f"TOMORROW {tomorrow_str} - {len(tomorrow_pt)} PT markets\n"
        for team,lst in by_team.items():
            o25=[x for x in lst if "2.5" in x["clean"]]
            o35=[x for x in lst if "3.5" in x["clean"]]
            if o25 and o35:
                a=max(o25, key=lambda x: (x["real"], x["vol"]))
                b=max(o35, key=lambda x: (x["real"], x["vol"]))
                # Middle profit when 3 goals = both win
                # Over 2.5 wins if >=3, Under 3.5 wins if <=3, so 3 = both win
                middles.append((a,b))
                tag_a="LIVE" if a["real"] else "EST"
                tag_b="LIVE" if b["real"] else "EST"
                msg+=f"\nMIDDLE {team}: O2.5 {a['over']}c [{tag_a}] + U3.5 {b['under']}c [{tag_b}] = {a['over']+b['under']-100} profit if 3 goals! Vol {a['vol']}/{b['vol']} {a['exp_pst']}\n"
            else:
                for s in lst[:2]:
                    tag="LIVE" if s["real"] else "EST"
                    msg+=f"{team} [{tag}] {s['clean']} {s['over']}c Vol {s['vol']} {s['exp_pst']}\n"
        
        if not middles:
            msg+=f"\nNo middle yet (need both O2.5 and U3.5 for same team)"
        send(msg)
    else:
        # No tomorrow - show next available
        by_date={}
        for s in soccer_pt:
            d=(s["exp_dt"]-timedelta(hours=7)).strftime("%m-%d")
            by_date.setdefault(d, []).append(s)
        sd=sorted(by_date.keys())
        if sd:
            msg=f"TOMORROW {tomorrow_str} - 0 PT in {len(ms)} markets\nNEXT {sd[0]} - {len(by_date[sd[0]])} games - Dates {sd[:4]}\nNote: Kalshi Point Total markets list close to game time, Moneyline may exist earlier\nWill increase to 2000+ markets after cooldown to find SAS-FIO 40% screenshot"
            send(msg)

def bot_loop():
    time.sleep(5)
    send(f"V90 FINAL PERFECT starting - 1000 markets + PST fix + Soccer only + 429 protection - Deploy OK if you see this!")
    while True:
        try:
            analyze()
            time.sleep(300)  # 5 min = No 429
        except Exception as e:
            print(f"loop err {e}")
            time.sleep(300)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V90 FINAL PERFECT running")
    def log_message(self,*a):
        pass

print(f"V90 PORT {PORT}")
threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
