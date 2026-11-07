import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))

def send(m):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":m[:4000]}, timeout=10)
    except:
        pass

sent=set()

def check():
    try:
        hits=[]
        # 5 leagues only - fast, no timeout
        for lg, lname in [("eng.1","EPL"),("esp.1","LaLiga"),("ita.1","Serie A"),("ger.1","Bundesliga"),("fra.1","Ligue1")]:
            try:
                r=requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/scoreboard", timeout=10)
                d=r.json()
                for ev in d.get("events",[]):
                    try:
                        comp=ev.get("competitions",[{}])[0]
                        if comp.get("status",{}).get("type",{}).get("state")!="in":
                            continue
                        disp=comp.get("status",{}).get("displayClock","")
                        try:
                            minute=int(str(disp).replace("'","").split("+")[0])
                        except:
                            minute=0
                        teams=comp.get("competitors",[])
                        if len(teams)<2:
                            continue
                        h=[t for t in teams if t.get("homeAway")=="home"][0]
                        a=[t for t in teams if t.get("homeAway")=="away"][0]
                        hs=int(h.get("score",0) or 0)
                        aws=int(a.get("score",0) or 0)
                        if abs(hs-aws)!=2:
                            continue
                        hn=h.get("team",{}).get("shortDisplayName","HOME")
                        an=a.get("team",{}).get("shortDisplayName","AWAY")
                        leader=hn if hs>aws else an
                        key=f"{ev.get('id')}_{hs}-{aws}"
                        if key in sent:
                            continue
                        sent.add(key)
                        hits.append(f"{lname} {minute}'\n{hn} {hs}-{aws} {an}\nLEAD 2: {leader}")
                    except:
                        continue
            except:
                continue
        if hits:
            send("⚽ LIVE 2-GOAL LEAD\n\n" + "\n\n".join(hits[:8]))
    except:
        pass

def loop():
    time.sleep(5)
    send("V203 LIVE starting - 2 Goal Lead ANY Minute - Deploy OK!")
    while True:
        try:
            check()
            time.sleep(60)
        except:
            time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V203 OK")
    def log_message(self,*a):
        pass

threading.Thread(target=loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
