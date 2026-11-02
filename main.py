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
    for i in range(20):  # 8000 markets to catch NEW-EVE Real 55%
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
            time.sleep(0.4)
        except:
            break
    return all_m

def team_name(m):
    y=(m.get("yes_sub_title","") or "")
    t=(m.get("title","") or "")
    s=(m.get("subtitle","") or "")
    # Try to find "vs" pattern
    for raw in [y, t, s]:
        low=raw.lower()
        # Skip garbage
        if low.strip() in ["yes","no","yes "]:
            continue
        if "leon" in low and "vs" not in low:
            continue
        if " vs " in low or " v " in low or "newcastle" in low or "everton" in low:
            # Clean
            txt=raw
            if " in " in txt:
                txt=txt.split(" in ")[-1]
            txt=txt.split("Over")[0].split("over")[0].strip()
            # Map known
            ll=txt.lower()
            if "newcastle" in ll and "everton" in ll:
                return "NEW-EVE"
            if "newcastle" in ll:
                return "NEW"
            if "everton" in ll:
                return "EVE"
            if "lorient" in ll and "brest" in ll:
                return "LOR-BRE"
            if "sassuolo" in ll:
                return "SAS-FIO"
            if "atalanta" in ll:
                return "ATA-PAR"
            if "cruz" in ll:
                return "CZ"
            if "tijuana" in ll:
                return "TJ"
            if "quilmes" in ll:
                return "QL"
            if "lanus" in ll:
                return "LN"
            if "vancouver" in ll:
                return "VAN"
            if "seattle" in ll:
                return "SEA"
            if "nashville" in ll:
                return "NSH"
            if "miami" in ll and "angeles" in ll:
                return "LA-MIA"
            if "miami" in ll:
                return "MIA"
            # Generic vs
            if " vs " in ll:
                parts=ll.split(" vs ")
                if len(parts)==2 and len(parts[0])>=2 and len(parts[1])>=2:
                    return parts[0][:3].upper()+"-"+parts[1][:3].upper()
    return ""

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V61 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.utcnow()
        for m in markets:
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(m.get("yes_sub_title","") or "")
            tl=title.lower()
            # Must have vs or known soccer
            if " vs " not in tl and "newcastle" not in tl and "everton" not in tl:
                if "cruz" not in tl and "miami" not in tl and "vancouver" not in tl and "seattle" not in tl:
                    # Keep but check over goals
                    pass
            if "both teams to score" in tl:
                continue
            if "edmonton" in tl or "ottawa" in tl or "lendeborg" in tl or "austin reaves" in tl or "yaxel" in tl or "leon" in tl:
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
            team=team_name(m)
            if not team:
                continue
            if team.lower() in ["yes","no","no leon","leon"]:
                continue
            clean="Over 2.5" if "2.5" in tl else "Over 3.5"
            real=ya_raw is not None and ya_raw!=0 or yb is not None and yb!=0
            soccer.append({"over":ya,"under":100-ya,"clean":clean,"team":team,"exp":exp_str[5:16] if exp_str else "","vol":m.get("volume",0) or 0,"real":real})

        soccer.sort(key=lambda x: (x["real"], x["vol"]), reverse=True)
        print(f"total {len(markets)} soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            real_cnt=sum(1 for s in soccer if s["real"])
            send(f"V61 FINAL Garbage Fixed - Total {len(markets)} Soccer {len(soccer)} (Real {real_cnt}) - NEW-EVE 55% Vol 2419 should appear")

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
                msg=f"MIDDLE {now} - {len(soccer)} games - {len(middles)} Middle EPL fixed\n\n"
                for i,(a,b) in enumerate(middles,1):
                    tag="LIVE" if a["real"] or b["real"] else "EST"
                    msg+=f"{i}. {a['team']} [{tag}]\n   O2.5 {a['over']}c + U3.5 {b['under']}c (O3.5 {b['over']}c)\n   Exp {b['exp']} Vol {b['vol']}\n   3 = both win | PRE 2 side | 15' U add | 70' JACKPOT O\n\n"
                send(msg)
            else:
                top=sorted([s for s in soccer if "2.5" in s["clean"]], key=lambda x: x["vol"], reverse=True)[:6]
                if top:
                    msg=f"TOP O2.5 {now} - {len(soccer)} games - Middle waiting\n\n"
                    for s in top:
                        tag="LIVE" if s["real"] else "EST"
                        msg+=f"{s['team']} [{tag}] O2.5 {s['over']}c Vol {s['vol']} Exp {s['exp']}\n"
                    send(msg)

    except Exception as e:
        print(f"err {e}")

def bot_loop():
    time.sleep(3)
    send("V61 starting garbage fixed 8000 scan")
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
        self.wfile.write(b"V61 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
