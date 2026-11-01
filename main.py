import requests, os, time
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.get(url, params={"chat_id": CHAT_ID, "text": msg})

def find_middle():
    sport = "soccer_epl"
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
    params = {"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "totals", "bookmakers": "pinnacle,bet365,unibet"}
    try:
        r = requests.get(url, params=params, timeout=15).json()
        for game in r:
            home = game['home_team']
            away = game['away_team']
            lines = []
            for bm in game.get('bookmakers', []):
                for market in bm.get('markets', []):
                    if market['key'] == 'totals':
                        for o in market['outcomes']:
                            lines.append({'bookie': bm['title'], 'name': o['name'], 'point': o['point'], 'price': o['price']})
            overs = [x for x in lines if x['name'] == 'Over' and x['point'] == 2.5 and x['price'] > 1.9]
            unders = [x for x in lines if x['name'] == 'Under' and x['point'] == 3.5 and x['price'] > 1.9]
            if overs and unders:
                best_over = max(overs, key=lambda x: x['price'])
                best_under = max(unders, key=lambda x: x['price'])
                msg = f"MIDDLE FOUND!\n{home} vs {away}\nOver 2.5 @ {best_over['price']} ({best_over['bookie']})\nUnder 3.5 @ {best_under['price']} ({best_under['bookie']})"
                send_telegram(msg)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    send_telegram("Bot Started - EPL Middle searching")
    while True:
        find_middle()
        time.sleep(300)
