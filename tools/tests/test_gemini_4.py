import urllib.request
import json
import os
import sys

# Get key directly from whatever env it ran before or command line
api_key = sys.argv[1] if len(sys.argv) > 1 else ""

if not api_key:
    print("NO API KEY PASSED")
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

