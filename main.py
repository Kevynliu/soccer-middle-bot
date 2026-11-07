import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))

def send(m):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":m[:3500]}, timeout=10)
    except:
        pass

# 【entity-ESPN¦canonical_name=ESPN】 leagues - EPL, LaLiga, Serie A, Bundesliga, Ligue1, etc
LEAGUES=[
 ("eng.1","EPL"),("esp.1","LaLiga"),("ita.1","Serie A"),
 ("ger.1","Bundesliga"),("fra.1","Ligue1"),("ned.1","Eredivisie"),
 ("por.1","Primeira"),("sco.1","Scotland"),("bel.1","Belgium"),
 ("usa.1","MLS"),("mex.1","Liga MX"),("bra.1","Brasileiro"),
 ("arg.1","Argentina"),("tur.1","Turkey"),("gre.1","Greece"),
]

sent=set()

def check():
    try:
        pst=datetime.utcnow()-timedelta(hours=7)
        hits=[]
        for lg, lname in LEAGUES:
            try:
                url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/scoreboard"
                r=requests.get(url, timeout=12)
                d=r.json()
                for ev in d.get("events",[]):
                    try:
                        comp=ev.get("competitions",[{}])[0]
                        status=comp.get("status",{})
                        st=status.get("type",{})
                        # minute
                        disp=status.get("displayClock","")
                        minute=0
                        try:
                            minute=int(str(disp).replace("'","").split("+")[0].split("-")[0])
                        except:
                            minute=0
                        state=st.get("state","")
                        if state!="in":
                            continue
                        # 65-70 only
                        if not (65 <= minute <= 70):
                            continue
                        teams=comp.get("competitors",[])
                        if len(teams)<2:
                            continue
                        home=[t for t in teams if t.get("homeAway")=="home"][0]
                        away=[t for t in teams if t.get("homeAway")=="away"][0]
                        hs=int(home.get("score",0) or 0)
                        aws=int(away.get("score",0) or 0)
                        total=hs+aws
                        diff=hs-aws
                        # RULE: total 2 goals + someone winning = 2-0 / 0-2
                        if total!=2 or diff==0:
                            continue
                        hn=home.get("team",{}).get("shortDisplayName","HOME")
                        an=away.get("team",{}).get("shortDisplayName","AWAY")
                        leader=hn if diff>0 else an
                        key=f"{ev.get('id')}_{minute}"
                        if key in sent:
                            continue
                        sent.add(key)
                        hits.append(f"{lname} {minute}'\n{hn} {hs}-{aws} {an}\nWinner now: {leader} - Total 2 goals\n65-70' Zone!")
                    except:
                        continue
            except:
                continue
        if hits:
            txt=f"⚽ LIVE 65-70' - 2 GOALS + WINNING - {pst.strftime('%H:%M PST')}\n\n" + "\n\n".join(hits[:8])
            send(txt)
            return len(hits)
        return 0
    except Exception as e:
        return 0

def loop():
    time.sleep(3)
    send(f"V200 LIVE 65-70' starting - 2 goals + winning only - Deploy OK!\nCheck every 60 sec - EPL LaLiga Serie A Bundesliga Ligue1 MLS + 10 leagues")
    while True:
        try:
            n=check()
            # every 60 sec check - 65-70 window is only 5 min!
            time.sleep(60)
        except:
            time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V200")
    def log_message(self,*a):
        pass

threading.Thread(target=loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
