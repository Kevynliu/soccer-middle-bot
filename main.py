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
            p={"status":"open","limit":200}
            if cursor: p["cursor"]=cursor
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code==429:
                print("429 wait 60s")
                time.sleep(60)
                continue
            if r.status_code!=200:
                print(f"API {r.status_code}")
                time.sleep(2)
                break
            d=r.json()
            batch=d.get("markets",[])
            if not batch:
                break
            all_ms.extend(batch)
            cursor=d.get("cursor")
            if not cursor:
                break
            time.sleep(0.5)
        except Exception as e:
            print(f"err {e}")
            time.sleep(2)
            break
    return all_ms

def analyze():
    ms=get_markets(total=5000)
    if not ms:
        return
    utc_now=datetime.utcnow()
    
    # === V92 FILTER - PROVEN WORKING (3000 -> 163 games) ===
    soccer_pt=[]
    for m in ms:
        # V92 exact filter that found 163 games
        tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
        t_title=(m.get("title","")+" "+m.get("subtitle","")).lower()
        
        if "2.5" not in tl and "3.5" not in tl:
            continue
        if "over" not in tl:
            continue
        if "goals scored" not in tl:
            continue
        if "edmonton" in tl or "ottawa" in tl or "both teams to score" in tl:
            continue
        
        exp=m.get("expiration_time","")
        try:
            exp_dt=datetime.fromisoformat(exp.replace("Z","")) if exp else None
            if not exp_dt or exp_dt < utc_now:
                continue
        except:
            continue
        
        ya=50
        real=False
        for v in [m.get("yes_ask"), m.get("yes_bid"), m.get("last_price")]:
            if v not in [None,0,"",0.0]:
                try:
                    ya=int(float(v))
                    if ya>0 and ya<100:
                        real=True
                        break
                except:
                    continue
        if ya<=0 or ya>=100:
            continue
        
        # Team clean
        team="SOC"
        low=tl
        if "【entity-sassuolo¦canonical_name=sassuolo】" in low and "【entity-fiorentina¦canonical_name=fiorentina】" in low: team="SAS-FIO"
        elif "【entity-sassuolo¦canonical_name=sassuolo】" in low: team="SAS"
        elif "【entity-fiorentina¦canonical_name=fiorentina】" in low: team="FIO"
        elif "【entity-newcastle¦canonical_name=newcastle】" in low and "【entity-everton¦canonical_name=everton】" in low: team="NEW-EVE"
        elif "【entity-newcastle¦canonical_name=newcastle】" in low: team="NEW"
        elif "【entity-everton¦canonical_name=everton】" in low: team="EVE"
        elif "atalanta" in low: team="ATA-PAR" if "【entity-parma¦canonical_name=parma】" in low else "ATA"
        elif "【entity-parma¦canonical_name=parma】" in low: team="PAR"
        elif "【entity-cruz azul¦canonical_name=cruz azul】" in low: team="CZ"
        elif "【entity-lorient¦canonical_name=lorient】" in low: team="LOR"
        elif "brest" in low: team="BRE"
        elif "【entity-inter miami¦canonical_name=inter miami】" in low or "lafc" in low: team="MIA"
        
        clean="O2.5" if "2.5" in tl else "O3.5"
        
        soccer_pt.append({
            "team":team, "clean":clean, "over":ya, "under":100-ya,
            "exp_dt":exp_dt, "exp_pst":(exp_dt-timedelta(hours=7)).strftime("%m-%d %H:%M PST"),
            "vol":m.get("volume",0) or 0, "real":real, "title":m.get("title",""), "ticker":m.get("ticker","")
        })

    # Group by same game (title base + date)
    games={}
    for s in soccer_pt:
        # Group key: team + date hour
        base=s["title"].lower().replace("over 2.5","").replace("over 3.5","").replace("goals scored","").strip()[:40]
        date_key=s["exp_dt"].strftime("%m-%d %H")
        gkey=f"{base}|{date_key}"
        if gkey not in games:
            games[gkey]= {"o25":[], "o35":[], "title":s["title"], "exp_pst":s["exp_pst"], "exp_dt":s["exp_dt"]}
        if "2.5" in s["clean"]:
            games[gkey]["o25"].append(s)
        else:
            games[gkey]["o35"].append(s)

    middles=[]
    for gkey,g in games.items():
        if g["o25"] and g["o35"]:
            # Best: cheapest cost
            best_o25=min(g["o25"], key=lambda x: x["over"])
            best_o35=min(g["o35"], key=lambda x: x["over"])  # O3.5 cheapest = U3.5 cheapest
            cost=best_o25["over"] + best_o35["under"]
            profit_3=200 - cost
            # Filter: cost <=110 and profit_3 >=5
            if cost <= 110 and profit_3 >= 0:
                middles.append({
                    "title":g["title"], "exp_pst":g["exp_pst"], "exp_dt":g["exp_dt"],
                    "o25":best_o25, "o35":best_o35, "cost":cost, "profit_3":profit_3
                })

    middles=sorted(middles, key=lambda x: (-x["profit_3"], x["cost"]))[:10]

    # === FIRST MESSAGE - Proven count ===
    if not hasattr(analyze,"first"):
        analyze.first=True
        by_date={}
        for s in soccer_pt:
            d=(s["exp_dt"]-timedelta(hours=7)).strftime("%m-%d")
            by_date[d]=by_date.get(d,0)+1
        sd=sorted(by_date.items())
        send(f"V94 FIXED - Deploy OK!\nScanned {len(ms)} -> Soccer PT {len(soccer_pt)} (V92 filter)\nGames {len(games)} -> Middles {len(middles)} (cost<=110)\nDates: {sd[:5]}\nNo spam, only real middles!")

    if middles:
        msg=f"🔥 {len(middles)} MIDDLE FOUND! 3 goals = both win 🔥\nScanned {len(ms)} markets\n\n"
        for i,m in enumerate(middles,1):
            tag_o="LIVE" if m["o25"]["real"] else "EST"
            tag_u="LIVE" if m["o35"]["real"] else "EST"
            clean_t=m["title"][:45]
            msg+=f"{i}. {clean_t}\n"
            msg+=f"   {m['o25']['clean']} {m['o25']['over']}c [{tag_o}] + U3.5 {m['o35']['under']}c [{tag_u}] (O3.5 {m['o35']['over']}c)\n"
            msg+=f"   Cost {m['cost']}c -> 3 goals = +{m['profit_3']}c | Vol {m['o25']['vol']}/{m['o35']['vol']} {m['exp_pst']}\n\n"
        send(msg)
    else:
        print(f"V94 No middle in {len(ms)} -> {len(soccer_pt)} PT -> {len(games)}
