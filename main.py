import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        if not BOT or not CHAT:
            print("Missing BOT or CHAT")
            return
        r=requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3000]}, timeout=10)
        print(f"send {r.status_code}")
    except Exception as e:
        print(f"send err {e}")

def analyze():
    try:
        # Only 1 batch 400 markets - ultra light
        p={"status":"open","limit":400}
        r=requests.get(f"{BASE}/markets", params=p, timeout=10)
        print(f"markets status {r.status_code}")
        if r.status_code!=200:
            send(f"V81 Test - Markets API {r.status_code} - BOT {BOT[:10]}")
            return
        data=r.json()
        ms=data.get("markets",[])
        soccer=[]
        for m in ms:
            tl=(m.get("title","")+" "+m.get("subtitle","")).lower()
            if "over" in tl and ("2.5" in tl or "3.5" in tl):
                if "edmonton" not in tl and "ottawa" not in tl:
                    soccer.append(tl[:60])
        send(f"V81 Ultra Minimal - Total 400 Soccer Over {len(soccer)} - Deploy OK! - Sample: {soccer[0][:40] if soccer else 'none'}")
    except Exception as e:
        print(f"analyze err {e}")
        send(f"V81 Error {str(e)[:200]}")

def bot_loop():
    time.sleep(3)
    send(f"V81 Ultra Minimal starting - 400 markets only - If you see this, Deploy OK!")
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
        self.wfile.write(b"V81 running")
    def log_message(self,*a):
        pass

print(f"V81 starting PORT {PORT} BOT {bool(BOT)} CHAT {bool(CHAT)}")
threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
