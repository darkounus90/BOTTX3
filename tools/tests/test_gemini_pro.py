import os
import sys
import google.generativeai as genai

# Asegurar que se use la API KEY de la sesión o del archivo bash profile/env
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("❌ ERROR: No se encontró la GEMINI_API_KEY en las variables de entorno.")
    sys.exit(1)

genai.configure(api_key=api_key)

try:
    print("🚀 Probando el modelo: gemini-2.5-pro")
    model = genai.GenerativeModel("models/gemini-2.5-pro")
    
    # Hacer una petición de prueba básica
    response = model.generate_content("Responde exactamente esto: '¡Hola! gemini-2.5-pro funciona perfectamente y sin bloqueos de cuota.'")
    
    print("\n✅ RESPUESTA DEL MODELO:")
    print("="*40)
    print(response.text)
    print("="*40)
    print("\n🎉 ¡El modelo gemini-2.5-pro está disponible y tu API key tiene acceso a él!")

except Exception as e:
    print("\n❌ FALLÓ LA PRUEBA.")
    print(f"Error devuelto por la API de Google:\n{e}")
    
    if "403" in str(e) or "429" in str(e):
        print("\n⚠️ DIAGNÓSTICO: Aunque el modelo existe, tu cuenta no tiene permisos gratuitos (403) o superaste la cuota (429) para usarlo en esta región/plan.")
