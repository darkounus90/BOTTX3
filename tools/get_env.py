import re
with open("config/.env", "r") as f:
    for line in f:
        if "GEMINI" in line:
            print(line.split("=")[1].strip()[:5] + "...")
