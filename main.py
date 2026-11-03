import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:2000]}, timeout=10)
    except:
        pass

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V108 running")
    def log_message(self,*a):
        pass

def bot_loop():
    time.sleep(2)
    send(f"V108 ULTRA TEST - Deploy OK! If you see this, Render is OK - No API call, just test!")
    while True:
        time.sleep(60)

print(f"V108 PORT {PORT} BOT {bool(BOT)}")
threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
