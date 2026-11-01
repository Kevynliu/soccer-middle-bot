import os, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
BOT_TOKEN=os.getenv("BOT_TOKEN") or os.getenv("Bot_TOKEN")
CHAT_ID=os.getenv("CHAT_ID") or os.getenv("Chat_ID")
def send(msg):
    try: requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",params={"chat_id":CHAT_ID,"text":msg},timeout=10)
    except: pass
def bot_loop():
    import time
    time.sleep(3)
    send("✅ Bot LIVE - Deployed!")
    while True: time.sleep(300)
class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"Bot running")
if __name__=="__main__":
    threading.Thread(target=bot_loop,daemon=True).start()
    HTTPServer(("0.0.0.0",int(os.getenv("PORT",10000))),H).serve_forever()
