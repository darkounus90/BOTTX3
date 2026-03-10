import os
import sys

api_key = "AIzaSyAgAV3K-t5rv_P7ru_NpyI8rcgGWObWkS8"
import google.generativeai as genai
genai.configure(api_key=api_key)

try:
    raw_models = list(genai.list_models())
    available_models = [m.name for m in raw_models if "generateContent" in m.supported_generation_methods]
except Exception as e:
    print(e)
    sys.exit(1)

target = None
t2_cands = [m for m in available_models if "2.5-flash" in m and "lite" not in m]
if t2_cands:
    target = t2_cands[0]

print(f"Target is {target}")
if target:
    m = genai.GenerativeModel(target)
    try:
        res = m.generate_content("Hola")
        print("OK", res.text)
    except Exception as e:
        print("FAIL", e)
