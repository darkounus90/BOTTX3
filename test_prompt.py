import os
import time

def parse_env():
    api_key = ""
    try:
        with open("config/.env", "r") as f:
            for line in f:
                if "GEMINI_API_KEY" in line:
                    api_key = line.split("=")[1].strip()
    except Exception:
        pass
    return api_key

key = parse_env()
print("KEY found in current directory config/.env length =", len(key))
