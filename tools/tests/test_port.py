from dashboard.app import app, socketio
import threading

def run():
    socketio.run(app, host="0.0.0.0", port=5050, allow_unsafe_werkzeug=True)

t = threading.Thread(target=run)
t.daemon = True
t.start()
import time
time.sleep(2)
print("Started")
import urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:5050/", timeout=1)
    print("Success connecting to 5050")
except Exception as e:
    print(f"Failed: {e}")
