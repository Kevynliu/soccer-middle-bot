import requests, os, time, threading
from http.server import HTTPServer, BaseHandler

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("Bot_TOKEN")
CHAT_ID = os.getenv("CHAT_ID") or os.getenv("Chat_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY") or os.getenv("Odds_API_KEY")
KALSHI_EMAIL = os.getenv("KALSHI_EMAIL") or os.getenv("Kalshi_EMAIL_1")
KALSHI_PASSWORD = os.getenv("KALSHI_PASSWORD") or os.getenv("Kalshi_PASSWORD")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

def get_kalshi_token():
    try:
        r = requests.post("https://api.elections.kalshi.com/trade-api/v2/login", json={"email": KALSHI_EMAIL, "password": KALSHI_PASSWORD}, timeout=15)
        return r.json().get("token")
    except: return None

def bot_loop():
    send_telegram("✅ Bot Started - 【entity-Kalshi¦canonical_name=Kalshi】+Odds Live")
    while True:
        token = get_kalshi_token()
        if token:
            print("【entity-Kalshi¦canonical_name=Kalshi】 OK")
        else:
            print("【entity-Kalshi¦canonical_name=Kalshi】 login fail")
        time.sleep(300)

# Web Service အတွက် port ဖွင့်ပေးတာ - ဒါပါမှ Render က Live လို့သတ်မှတ်တာ
class Handler(BaseHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

threading.Thread(target=bot_loop, daemon=True).start()
run_web()
