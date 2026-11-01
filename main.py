import requests, os, time
BOT_TOKEN = os.getenv("Bot_TOKEN")
CHAT_ID = os.getenv("Chat_ID")
ODDS_API_KEY = os.getenv("Odds_API_KEY")
KALSHI_EMAIL = os.getenv("Kalshi_EMAIL_1")
KALSHI_PASSWORD = os.getenv("Kalshi_PASSWORD")

# Render မှာ Key နာမည် နဲနဲကွဲရင် အောက်က ၂ ကြောင်းကို ပြင်ပေးမယ် - အခု မင်းပုံထဲက နာမည်နဲ့ ကိုက်အောင် ရေးထားတယ်
# တကယ်က Bot_TOKEN, Chat_ID စသည်ဖြင့် ဖြစ်နေလို့ အပေါ်က get တွေက case-sensitive ဖြစ်တယ်
# အလွယ်ဆုံး - အောက်က ကို သုံးပါ (Key နာမည်အတိအကျ)
BOT_TOKEN = os.getenv("Bot_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("Bot_...")
CHAT_ID = os.getenv("Chat_ID") or os.getenv("CHAT_ID") or os.getenv("CHATID")
ODDS_API_KEY = os.getenv("Odds_API_KEY") or os.getenv("ODDS_API_KEY")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(e)

def get_kalshi_token():
    try:
        url = "https://api.elections.kalshi.com/trade-api/v2/login"
        r = requests.post(url, json={"email": KALSHI_EMAIL, "password": KALSHI_PASSWORD}, timeout=15)
        print(r.text)
        return r.json().get("token")
    except Exception as e:
        print(f"Kalshi login error {e}")
        return None

def check_combined():
    print("Checking...")
    token = get_kalshi_token()
    if not token:
        send_telegram("❌ 【entity-Kalshi¦canonical_name=Kalshi】 login failed - Email/Pass စစ်ပါ")
        return
    send_telegram("✅ 【entity-Kalshi¦canonical_name=Kalshi】 login OK - Market ရှာနေပြီ")
    # ဒီနေရာမှာ Kalshi market ရှာတဲ့ logic ဆက်ရေးလို့ရပြီ

if __name__ == "__main__":
    send_telegram("✅ Bot Started - Kalshi+Odds checking")
    while True:
        check_combined()
        time.sleep(300)
