import os
import sys

# Leer la KEY del archivo .env oculto que tienes en tu proyecto
api_key = os.environ.get("GEMINI_API_KEY", "")
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
        try:
            with open(".env", "r") as f:
                for line in f:
                    if "GEMINI_API_KEY" in line:
                        api_key = line.split("=")[1].strip()
                        break
        except:
            pass

if not api_key:
    print("❌ No se encontró la API KEY")
    sys.exit(1)

import google.generativeai as genai
genai.configure(api_key=api_key)

print("🔍 Buscando modelos que sí permitan generar contenido...")
try:
    models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
except Exception as e:
    print(f"Error listando modelos: {e}")
    sys.exit(1)

if not models:
    print("❌ Tu API Key no tiene permiso para usar ningún modelo.")
    sys.exit(1)

print(f"Modelos disponibles: {len(models)}")
print("-" * 50)

for m_name in models:
    if "vision" in m_name or "embedding" in m_name:
        continue # Omitir modelos viejos o de embeddings
        
    print(f"Probando {m_name}...", end=" ")
    model = genai.GenerativeModel(model_name=m_name)
    try:
        resp = model.generate_content("Responde solo OK si funcionó")
        print("✅ FUNCIONA! ->", resp.text.strip())
    except Exception as e:
        err_msg = str(e)
        if "limit: 0" in err_msg:
            print("❌ BLOQUEADO (Límite: 0 peticiones en Free Tier)")
        elif "429" in err_msg:
            print("❌ BLOQUEADO (Por Cuota/Rate Limit)")
        else:
            print(f"❌ ERROR: {e}")
            
print("-" * 50)
print("Prueba finalizada.")
