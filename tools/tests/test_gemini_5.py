import urllib.request
import json
import os
import sys

# Get key directly from whatever env it ran before or command line
api_key = sys.argv[1]

# Try models:
for model_name in ["gemini-1.5-flash", "gemini-2.0-flash"]:
    print(f"\n--- Testing {model_name} ---")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = json.dumps({"contents":[{"parts":[{"text":"RESPOND STRICTLY WITH 'HI'"}]}]}).encode('utf-8')

    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            text = result['candidates'][0]['content']['parts'][0]['text']
            print("Success:", text)
    except Exception as e:
        print("Error:", getattr(e, "code", str(e)), getattr(e, "reason", ""))
        try:
            print("Response text:", e.read().decode("utf-8"))
        except:
            pass

