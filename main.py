import requests, os, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("Bot_TOKEN") or os.getenv("Bot_") or ""
CHAT_ID = os.getenv("CHAT_ID") or os.getenv("Chat_ID") or os.getenv("Chat_") or ""
ODDS_API_KEY = os.getenv("ODDS_API_KEY") or os.getenv("Odds_API_KEY") or ""
KALSHI_EMAIL = os.getenv("KALSHI_EMAIL") or os.getenv("Kalshi_EMAIL_1") or ""
KALSHI_PASSWORD = os.getenv("KALSHI_PASSWORD") or os.getenv("Kalshi_PASSWORD") or ""

def send_telegram(msg):
    try:
        if not BOT_TOKEN or not CHAT_ID: return
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        print(f"Telegram sent: {msg}")
    except Exception as e:
        print(f"TG error: {e}")

def get_kalshi_token():
    try:
        if not KALSHI_EMAIL or not KALSHI_PASSWORD: return None
        url = "https://api.elections.kalshi.com/trade-api/v2/login"
        r = requests.post(url, json={"email": KALSHI_EMAIL, "password": KALSHI_PASSWORD}, timeout=15)
        print(f"【entity-Kalshi¦canonical_name=KALSHI】 login: {r.text[:200]}")
        return r.json().get("token")
    except Exception as e:
        print(f"【entity-Kalshi¦canonical_name=KALSHI】 error: {e}")
        return None

def bot_loop():
    time.sleep(5)
    send_telegram("✅ Bot is LIVE - Kalshi+Odds checking")
    while True:
        try:
            token = get_kalshi_token()
            if token:
                print("Kalshi OK")
            else:
                print("Kalshi login waiting...")
            time.sleep(300)
        except Exception as e:
            print(e)
            time.sleep(60)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running - OK")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    print(f"Starting web on {port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=bot_loop, daemon=True).start()
    run_web()
