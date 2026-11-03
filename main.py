import os, time, requests, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

BOT=os.getenv("BOT_TOKEN","").strip()
CHAT=os.getenv("CHAT_ID","").strip()
PORT=int(os.getenv("PORT","10000"))
BASE="https://api.elections.kalshi.com/trade-api/v2"

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id":CHAT,"text":msg[:3500]}, timeout=10)
    except:
        pass

def analyze():
    try:
        r=requests.get(f"{BASE}/markets", params={"status":"open","limit":1000}, timeout=15)
        if r.status_code!=200:
            send(f"V110 API {r.status_code}")
            return
        ms=r.json().get("markets",[])
        utc_now=datetime.utcnow()
        
        # DEBUG: Sample first 20 titles
        sample=[]
        for m in ms[:20]:
            sample.append(f"{m.get('title','')[:50]}")
        
        # Check for goals scored anywhere
        goals_count=0
        over_count=0
        for m in ms:
            tl=(m.get("title","")+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "goals scored" in tl:
                goals_count+=1
            if "over" in tl and ("2.5" in tl or "3.5" in tl):
                over_count+=1
        
        # Try looser filter - just over 2.5/3.5
        soccer_loose=[]
        soccer_strict=[]
        for m in ms:
            title=m.get("title","")
            tl=(title+" "+m.get("subtitle","")+" "+m.get("yes_sub_title","")).lower()
            if "2.5" in tl or "3.5" in tl:
                if "over" in tl:
                    soccer_loose.append(title[:60])
                    if "goals scored" in tl:
                        soccer_strict.append(title[:60])
        
        if not hasattr(analyze,"first"):
            analyze.first=True
            msg=f"V110 DEBUG - Deploy OK!\nScanned {len(ms)} markets\n"
            msg+=f"'goals scored' in 1000: {goals_count}\n"
            msg+=f"'over 2.5/3.5' in 1000: {over_count}\n"
            msg+=f"Strict (goals+over+2.5): {len(soccer_strict)}\n"
            msg+=f"Loose (over+2.5): {len(soccer_loose)}\n\n"
            msg+=f"Sample titles first 5:\n"
            for i,t in enumerate(sample[:5],1):
                msg+=f"{i}. {t}\n"
            msg+=f"\nSoccer strict sample:\n"
            for t in soccer_strict[:3]:
                msg+=f"{t}\n"
            send(msg)

    except Exception as e:
        send(f"V110 Error {str(e)[:150]}")

def bot_loop():
    time.sleep(3)
    send(f"V110 DEBUG starting - Check what's in 1000 markets now - Deploy OK!")
    while True:
        try:
            analyze()
            time.sleep(600)
        except:
            time.sleep(600)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"V110 running")
    def log_message(self,*a):
        pass

threading.Thread(target=bot_loop, daemon=True).start()
HTTPServer(("0.0.0.0", PORT), H).serve_forever()
