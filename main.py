import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=20)
    except:
        pass

def get_all():
    all_m=[]
    cur=None
    for i in range(40):  # 40*400=16000 markets - to catch NEW-EVE beyond 6000
        try:
            p={"status":"open","limit":400}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            if r.status_code!=200:
                print(f"batch {i} status {r.status_code}")
                break
            data=r.json()
            ms=data.get("markets",[])
            if not ms:
                break
            all_m.extend(ms)
            cur=data.get("cursor")
            print(f"batch {i} got {len(ms)} total {len(all_m)}")
            if not cur:
                break
            time.sleep(0.25)
        except Exception as e:
            print(f"batch {i} err {e}")
            break
    return all_m

def get_ob_price(ticker):
    try:
        r=requests.get(f"{BASE}/markets/{ticker}/orderbook", timeout=10)
        print(f"OB {ticker} status {r.status_code}")
        if r.status_code!=200:
            return None
        data=r.json()
        # Print keys for debug
        ob=data.get("orderbook", data)
        print(f"OB keys {list(ob.keys())[:5]}")
        # Try all possible structures
        for k in ["yes","yes_dollars","no","no_dollars","bids","asks"]:
            arr=ob.get(k,[])
            if arr and len(arr)>0:
                try:
                    first=arr[0]
                    if isinstance(first, (list,tuple)):
                        price=float(first[0])
                    else:
                        price=float(first)
                    if price>1:
                        price=price/100
                    if "no" in k.lower():
                        price=1-price
                    if 0.05 <= price <= 0.95:
                        print(f"OB {ticker} found {k} {price}")
                        return int(price*100)
                except Exception as e:
                    print(f"OB parse err {e}")
                    continue
    except Exception as e:
        print(f"OB err {e}")
    return None

def team_name(m):
    txt=(m.get("yes_sub_title","")+" "+m.get("title","")+" "+m.get("subtitle","")+" "+m.get("event_ticker","")).lower()
    if "newcastle" in txt and "everton" in txt:
        return "NEW-EVE"
    if "newcastle" in txt:
        return "NEW"
    if "everton" in txt:
        return "EVE"
    if "lorient" in txt:
        return "LOR-BRE"
    if "sassuolo" in txt or "fiorentina" in txt:
        return "SAS-FIO"
    if "atalanta" in txt or "parma" in txt:
        return "ATA-PAR"
    if "cruz" in txt:
        return "CZ"
    if "tijuana" in txt:
        return "TJ"
    if "vancouver" in txt:
        return "VAN"
    if "seattle" in txt:
        return "SEA"
    if "nashville" in txt:
        return "NSH"
    if "miami" in txt:
        return "MIA"
    if "vs" in txt:
        # fallback generic
        return "SOCCER"
    return ""

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V65 {now}")
    try:
        markets=get_all()
        soccer=[]
        now_utc=datetime.utcnow()
        for m in markets:
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")+" "+(
