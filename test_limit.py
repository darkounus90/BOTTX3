import os
import sys
import time

api_key = "AIzaSyAgAV3K-t5rv_P7ru_NpyI8rcgGWObWkS8"
import google.generativeai as genai
genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-2.5-flash")

print("🔍 Iniciando prueba de resistencia (Más de 20 peticiones a gemini-2.5-flash)...")
try:
    for i in range(1, 23):
        # Hacemos pausas de 4 segundos para evitar el Rate Limit por Minuto (15 RPM)
        # Esto nos asegura probar el límite real diario o de sesión sin disparar el spam-block
        resp = model.generate_content(f"Responde solo el numero {i}")
        print(f"Petición {i}/22 -> ÉXITO: {resp.text.strip()}")
        time.sleep(4.5)
        
    print("\n✅ ¡PRUEBA SUPERADA! El modelo gemini-2.5-flash permite más de 20 peticiones seguidas.")
except Exception as e:
    err_str = str(e).lower()
    if "429" in err_str or "quota" in err_str:
        print(f"\n❌ BLOQUEO DE CUOTA en la petición {i}: {e}")
    else:
        print(f"\n❌ ERROR INESPERADO en la petición {i}: {e}")
