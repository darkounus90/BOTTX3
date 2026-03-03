import os
import sys

# La Key que extraje de START_BOT_AND_AI.bat
api_key = "AIzaSyAgAV3K-t5rv_P7ru_NpyI8rcgGWObWkS8"

import google.generativeai as genai
genai.configure(api_key=api_key)

print("🔍 Buscando modelos que sí permitan generar contenido con esta Key...")
try:
    models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
except Exception as e:
    print(f"Error listando modelos: {e}")
    sys.exit(1)

if not models:
    print("❌ Tu API Key no tiene permiso para usar ningún modelo.")
    sys.exit(1)

print(f"Modelos disponibles encontrados: {len(models)}")
print("-" * 50)

for m_name in models:
    if "vision" in m_name or "embedding" in m_name or "text-bison" in m_name:
        continue # Omitir viejos modelos Legacy
        
    print(f"Probando {m_name}...", end=" ")
    model = genai.GenerativeModel(model_name=m_name)
    try:
        resp = model.generate_content("Responde ok")
        print("✅ FUNCIONA! ->", resp.text.strip())
    except Exception as e:
        err_msg = str(e)
        if "limit: 0" in err_msg:
            print("❌ BLOQUEADO (Límite: 0 peticiones en Free Tier)")
        elif "429" in err_msg or "quota" in err_msg.lower():
            print("❌ BLOQUEADO (Por Cuota/Rate Limit Exhausted)")
        else:
            print(f"❌ ERROR: {e}")
            
print("-" * 50)
print("Prueba finalizada.")
