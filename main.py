import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta

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

def team_name(m):
    y=(m.get("yes_sub_title","") or "").lower()
    t=(m.get("title","") or "").lower()
    raw=y+" "+t
    if "【entity-cruz azul¦canonical_name=Cruz Azul】" in raw:
        return "【entity-Cruz Azul¦canonical_name=Cruz Azul】"
    if "tijuana" in raw:
        return "Tijuana"
    if "quilmes" in raw:
        return "Quilmes"
    if "lanus" in raw:
        return "Lanus"
    if "vancouver" in raw:
        return "Vancouver"
    if "【entity-seattle¦canonical_name=Seattle Sounders FC】" in raw:
        return "【entity-Seattle¦canonical_name=Seattle Sounders FC】"
    if "nashville" in raw:
        return "Nashville"
    if "los angeles" in raw and "miami" in raw:
        return "LAFC vs Miami"
    if "【entity-palmeiras¦canonical_name=Palmeiras】" in raw:
        return "【entity-Palmeiras¦canonical_name=Palmeiras】"
    if "gremio" in raw:
        return "Gremio"
    if "miami" in raw:
        return "Miami"
    return ""

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V53 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.now(timezone.utc)
        limit_48=now_utc+timedelta(hours=48)
        for m in markets:
            series=(m.get("series_ticker","") or "").upper()
            ev=(m.get("event_ticker","") or "").upper()
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
            if "SOCCER" not in series and "SOCCER" not in ev:
                if not any(x in tl for x in ["【entity-cruz azul¦canonical_name=Cruz Azul】","tijuana","quilmes","lanus","vancouver","【entity-seattle¦canonical_name=Seattle Sounders FC】","nashville","【entity-palmeiras¦canonical_name=Palmeiras】","gremio","miami","mls"]):
                    continue
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
            # Real price
            ya=None
            yb=m.get("yes_bid")
            ya_raw=m.get("yes_ask")
            lp=m.get("last_price")
            # Try best: if both bid/ask, avg, else last_price
            try:
                if ya_raw is not None and yb is not None and ya_raw!=0 and yb!=0:
                    ya=int((float(ya_raw)+float(yb))/2)
                elif ya_raw is not None and ya_raw!=0:
                    ya=int(float(ya_raw))
                elif yb is not None and yb!=0:
                    ya=int(float(yb))
                elif lp is not None and lp!=0:
                    ya=int(float(lp))
            except:
                pass
            if ya is None:
                ya=50
            if not (5 <= ya <= 95):
                continue
            exp=m.get("expiration_time","")
            exp_dt=None
            try:
                if exp:
                    exp_dt=datetime.fromisoformat(exp.replace("Z","+00:00"))
                    if exp_dt < now_utc:
                        continue
                    if exp_dt > limit_48:
                        continue
            except:
                pass
            team=team_name(m)
            if not team:
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            # Volume check - prioritize Vol>0
            vol=m.get("volume",0) or 0
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"ev":ev,"vol":vol,"exp":exp[5:16] if exp else "","exp_dt":exp_dt,"real":ya_raw is not None or yb is not None})

        # Sort by real price + volume first
        soccer.sort(key=lambda x: (x["real"], x["vol"]), reverse=True)
        print(f"total {len(markets)} soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            real_cnt=sum(1 for s in soccer if s["real"])
            send(f"V53 FINAL 48h Live - Total {len(markets)} Soccer {len(soccer)} (Real price {real_cnt}) - 48h only")

        if soccer:
            by_team={}
            for s in soccer:
                k=s["team"]+"_"+(s["exp"][:5] if s["exp"] else "na")
                base=s["team"]
                if base not in by_team:
                    by_team[base]=[]
                by_team[base].append(s)

            middles=[]
            for team, lst in by_team.items():
                o25=[x for x in lst if "2.5" in x["clean"]]
                o35=[x for x in lst if "3.5" in x["clean"]]
                if o25 and o35:
                    a=min(o25, key=lambda x: x["over"])
                    b=min(o35, key=lambda x: x["over"])
                    middles.append((a,b))

            middles=sorted(middles, key=lambda x: x[0]["vol"], reverse=True)[:5]
            if middles:
                msg=f"PRE-MATCH MIDDLE {now} - {len(soccer)} Soccer 48h - {len(middles)} Middle\n\n"
                for i,(a,b) in enumerate(middles,1):
                    live_tag=" [LIVE PRICE]" if a["real"] or b["real"] else " [50c est]"
                    msg+=f"{i}. {a['team']}{live_tag}\n   Over 2.5 {a['over']}c + Under 3.5 {b['under']}c (Over 3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n   3 goals = both win | PRE: 2 side buy | 15' 0-0 Under add | 70' Jackpot Over\n\n"
                send(msg)
            else:
                top=soccer[:5]
                msg=f"PRE-MATCH {now} - {len(soccer)} Soccer 48h - Middle waiting\n"
                for s in top:
                    msg+=f"{s['team']} {s['clean']} {s['over']}c Vol {s['vol']} Exp {s['exp']}\n"
                send(msg)

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(3)
    send("V53 starting 48h + real price")
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
        self.wfile.write(b"V53 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
