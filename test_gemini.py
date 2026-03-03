import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY", "")
print("KEY length:", len(api_key))

try:
    genai.configure(api_key=api_key)
    # Check if we can find the model
    models = list(genai.list_models())
    pro_models = [m.name for m in models if "2.5-pro" in m]
    print("Found 2.5-pro models:", pro_models)
    
    if pro_models:
        model_name = pro_models[0]
        print("Using model:", model_name)
        model = genai.GenerativeModel(model_name)
        prompt = "Responde OK si me recibes."
        res = model.generate_content(prompt)
        print("RESPONSE:", res.text)
    else:
        print("2.5-pro not found in list")
        
except Exception as e:
    import traceback
    traceback.print_exc()
