import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3000]}, timeout=10)
    except:
        pass

def analyze():
    try:
        p={"status":"open","limit":400}
        r=requests.get(f"{BASE}/markets", params=p, timeout=10)
        if r.status_code!=200:
            send(f"V84 API {r.status_code}")
            return
        ms=r.json().get("markets",[])
        soccer=[]
        nba_filtered=0
        for m in ms:
            tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "2.5" not in tl and "3.5" not in tl:
                continue
            if "over" not in tl:
                continue
            # FIX: must have goals scored = Soccer only, filter NBA
            if "goals scored" not in tl:
                if "wins by over" in tl or "point" in tl:
                    nba_filtered+=1
                continue
            if "edmonton" in tl or "ottawa" in tl:
                continue
            soccer.append(tl[:70])
        send(f"V84 Minimal 400 - Deploy OK! - Soccer PT {len(soccer)} (no NBA, filtered {nba_filtered} NBA) - Total 400 - Sample: {soccer[0][:40] if soccer else 'none'}")
    except Exception as e:
        send(f"V84 Error {str(e)[:200]}")

def bot_loop():
    time.sleep(2)
    send(f"V84 Minimal 400 starting - Fixed Filter Soccer Only - If you see this, Deploy OK!")
    while True:
        try:
            analyze()
            time.sleep(180)
        except:
            time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V84 running")
    def log_message(self,*a):
        pass

print(f"V84 PORT {PORT} BOT {bool(BOT)}")
threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
