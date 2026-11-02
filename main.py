import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))

def send(msg):
    try:
        if not BOT or not CHAT:
            print(f"Missing BOT {bool(BOT)} CHAT {bool(CHAT)}")
            return
        r=requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=15)
        print(f"send {r.status_code}")
    except Exception as e:
        print(f"send err {e}")

def bot_loop():
    time.sleep(2)
    send(f"V67 TEST - PORT {PORT} BOT {BOT[:10]}... - If you see this, Render Deploy OK!")
    while True:
        try:
            send(f"PING {time.strftime('%H:%M:%S')} - Deploy OK - 【entity-Kalshi¦canonical_name=Kalshi】 logic will be added after this test")
            time.sleep(120)
        except Exception as e:
            print(e)
            time.sleep(60)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V67 TEST running - Deploy OK")
    def log_message(self,*a):
        pass

print(f"Starting V67 TEST on PORT {PORT} BOT set {bool(BOT)}")
threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
