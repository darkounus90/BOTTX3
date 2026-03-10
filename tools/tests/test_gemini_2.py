import google.generativeai as genai
import os

api_key = os.environ.get("GEMINI_API_KEY", "")

# if empty, try to get from config/.env
if not api_key:
    try:
        with open("config/.env", "r") as f:
            for line in f:
                if "GEMINI_API_KEY" in line:
                    api_key = line.split("=")[1].strip()
                    break
    except:
        pass

if not api_key:
    # Try parent directory .env
    try:
        with open(".env", "r") as f:
            for line in f:
                if "GEMINI_API_KEY" in line:
                    api_key = line.split("=")[1].strip()
                    break
    except:
        pass

print("Len key:", len(api_key))
genai.configure(api_key=api_key)

try:
    available_models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
    t2_cands = [m for m in available_models if "2.0-flash" in m]
    
    if t2_cands:
        target = t2_cands[0]
        model = genai.GenerativeModel(model_name=target)
        try:
            res = model.generate_content("RESPOND STRICTLY WITH 'HI'")
            print("Response 2.0-flash:", res.text)
        except Exception as ex:
            print("Error calling 2.0-flash:", ex)
except Exception as e:
    import traceback
    traceback.print_exc()
