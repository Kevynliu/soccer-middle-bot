import os, requests, threading, time
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
print(f"DEBUG BOT_TOKEN len={len(BOT)} CHAT_ID={CHAT}", flush=True)

def send(m):
    try:
        r=requests.get(f"https://api.telegram.org/bot{BOT}/sendMessage", params={"chat_id":CHAT,"text":m}, timeout=10)
        print(f"TG response: {r.text[:200]}", flush=True)
    except Exception as e:
        print(f"TG error {e}", flush=True)

def loop():
    time.sleep(3)
    send("✅ Bot LIVE - Test message")
    while True:
        time.sleep(60)
        send("💓 Bot alive")

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Bot is running - OK")
    def log_message(self,*a): pass

threading.Thread(target=loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
