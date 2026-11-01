import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg}, timeout=20)
        print("sent")
    except Exception as e:
        print(f"send err {e}")

def get_all():
    all_m=[]
    cur=None
    for i in range(10):
        try:
            p={"status":"open","limit":400}
            if cur:
                p["cursor"]=cur
            r=requests.get(f"{BASE}/markets", params=p, timeout=20)
            print(f"fetch {i} {r.status_code}")
            if r.status_code!=200:
                time.sleep(1)
                continue
            data=r.json()
            ms=data.get("markets",[])
            all_m.extend(ms)
            cur=data.get("cursor")
            if not cur:
                break
            time.sleep(0.5)
        except Exception as e:
            print(f"get err {e}")
            break
    return all_m

def analyze():
    now=time.strftime("%H:%M:%S")
    print(f"V41 {now}")
    try:
        markets=get_all()
        print(f"total {len(markets)}")
        soccer=[]
        for m in markets:
            title=(m.get("title","") or "")+" "+(m.get("subtitle","") or "")
            tl=title.lower()
            if "over" in tl and "goals scored" in tl and "2.5" in tl:
                soccer.append(m)
            if "over" in tl and "goals scored" in tl and "3.5" in tl:
                soccer.append(m)
        print(f"soccer {len(soccer)}")
        if not hasattr(analyze,"first"):
            analyze.first=True
            send(f"V41 MINIMAL Live - Total {len(markets)} Soccer {len(soccer)} - Deploy fix")
        else:
            if len(soccer) > 0:
                msg=f"PRE-MATCH {now} - {len(soccer)} Soccer Over 2.5/3.5\n"
                for s in soccer[:3]:
                    msg+=f"{s.get('title','')[:40]} {s.get('ticker','')[:20]}\n"
                send(msg)
    except Exception as e:
        print(f"analyze err {e}")
        send(f"Error {e}")

def bot_loop():
    time.sleep(3)
    send("V41 starting")
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
        self.wfile.write(b"V41 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", int(os.getenv("PORT","10000"))), H).serve_forever()
