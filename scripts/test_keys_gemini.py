import google.generativeai as genai
import sys

# Extraemos las llaves mapeadas en los bats/scripts del sistema
keys = [
    "AIzaSyAgAV3K-t5rv_P7ru_NpyI8rcgGWObWkS8",
    "AIzaSyC1OgAyHJKbauD_-S9ohpGGpdsmLDFrO-4"
]

models_to_test = [
    "models/gemini-2.0-flash", 
    "models/gemini-2.5-flash", 
    "models/gemma-3-4b-it"
]

print("🔍 Iniciando Test de Diagnóstico de API Keys de Gemini...")
print("==========================================================")

for idx, key in enumerate(keys):
    print(f"\n🔑 PROBANDO LLAVE #{idx + 1}: {key[:15]}...***")
    genai.configure(api_key=key)
    
    for m in models_to_test:
        try:
            model = genai.GenerativeModel(m)
            # Imponemos timeout para que no se quede colgado eternamente
            response = model.generate_content("Responde corto: OK", request_options={"timeout": 15})
            print(f"  [ 🟢 {m.replace('models/', '')} ] SUCCESS -> Respuesta: {response.text.strip()}")
        except Exception as e:
            err_msg = str(e).splitlines()[0] if str(e) else "Error desconocido"
            if "403" in str(e):
                err_msg = "403 Forbidden (Proyecto sin acceso / Términos no aceptados)"
            elif "429" in str(e) or "quota" in str(e).lower():
                err_msg = "429 Quota Excedida / Rate Limit"
            print(f"  [ 🔴 {m.replace('models/', '')} ] FAILED -> {err_msg}")

print("\n==========================================================")
print("Diagnostic finalizado. Si alguna de las llaves te da 403 en gemma-3,")
print("significa que no tienes habilitado ese modelo en esta API Key.")
print("==========================================================")
