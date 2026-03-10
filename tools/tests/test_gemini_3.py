import urllib.request
import json
import os

api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    try:
        with open(".env", "r") as f:
            for line in f:
                if "GEMINI_API_KEY" in line:
                    api_key = line.split("=")[1].strip()
                    break
    except:
        pass

if not api_key:
    print("NO API KEY")
    exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
headers = {'Content-Type': 'application/json'}
data = json.dumps({"contents":[{"parts":[{"text":"RESPOND STRICTLY WITH 'HI'"}]}]}).encode('utf-8')

req = urllib.request.Request(url, data=data, headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        text = result['candidates'][0]['content']['parts'][0]['text']
        print("Success 2.0-flash:", text)
except Exception as e:
    print("Error 2.0-flash:", getattr(e, "code", str(e)), getattr(e, "reason", ""))

# Test 2.5-pro
url_pro = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"
req_pro = urllib.request.Request(url_pro, data=data, headers=headers)
try:
    with urllib.request.urlopen(req_pro) as response:
        result = json.loads(response.read().decode('utf-8'))
        text = result['candidates'][0]['content']['parts'][0]['text']
        print("Success 2.5-pro:", text)
except Exception as e:
    print("Error 2.5-pro:", getattr(e, "code", str(e)), getattr(e, "reason", ""))
