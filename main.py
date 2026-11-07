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

LEAGUES=[
 ("eng.1","EPL"),("esp.1","LaLiga"),("ita.1","Serie A"),
 ("ger.1","Bundesliga"),("fra.1","Ligue1"),("ned.1","Eredivisie"),
 ("por.1","Primeira"),("sco.1","Scotland"),("bel.1","Belgium"),
 ("usa.1","MLS"),("mex.1","Liga MX"),("bra.1","Brasileiro"),
 ("arg.1","Argentina"),("tur.1","Turkey"),("gre.1","Greece"),
 ("chn.1","China"),("jpn.1","J-League"),("kor.1","K-League"),
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
                        if st.get("state")!="in":
                            continue
                        disp=status.get("displayClock","")
                        try:
                            minute=int(str(disp).replace("'","").split("+")[0].split("-")[0])
                        except:
                            minute=0
                        teams=comp.get("competitors",[])
                        if len(teams)<2:
                            continue
                        home=[t for t in teams if t.get("homeAway")=="home"][0]
                        away=[t for t in teams if t.get("homeAway")=="away"][0]
                        hs=int(home.get("score",0) or 0)
                        aws=int(away.get("score",0) or 0)
                        diff=hs-aws
                        # RULE: 2 goals difference - ANY MINUTE
                        # 2-0, 0-2, 3-1, 1-3, 4-2, 2-4, 5-3, 3-5
                        if abs(diff)!=2:
                            continue
                        hn=home.get("team",{}).get("shortDisplayName","HOME")
                        an=away.get("team",{}).get("shortDisplayName","AWAY")
                        leader=hn if diff>0 else an
                        key=f"{ev.get('id')}_{hs}-{aws}"
                        if key in sent:
                            continue
                        sent.add(key)
                        hits.append(f"{lname} {minute}'\n{hn} {hs}-{aws} {an}\nLEAD 2 GOALS: {leader} ✅")
                    except:
                        continue
            except:
                continue
        if hits:
            txt=f"⚽ LIVE 2-GOAL LEAD - {pst.strftime('%H:%M PST')}\n\n" + "\n\n".join(hits[:10])
            send(txt)
            return len(hits)
        return 0
    except:
        return 0

def loop():
   
