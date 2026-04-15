import sys
import os
import json

# Agregar la raíz del proyecto para poder importar core y config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.llm_oracle import GeminiOracle

class DummyLogger:
    def __init__(self): pass
    def info(self, msg): print(f"[INFO] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def debug(self, msg): print(f"[DEBUG] {msg}")

def main():
    print("\n" + "="*60)
    print(" 🧠 INICIANDO TEST DE INTEGRACIÓN DEL ORÁCULO IA")
    print("="*60 + "\n")
    
    # Simular un logger aislado
    logger = DummyLogger()
    
    # Extraer la clave desde el BOT CONFIG como lo hace main.py
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        api_key = "AIzaSyAgAV3K-t5rv_P7ru_NpyI8rcgGWObWkS8,AIzaSyC1OgAyHJKbauD_-S9ohpGGpdsmLDFrO-4"
        os.environ["GEMINI_API_KEY"] = api_key
        print("⚠️ Variables de entorno no detectadas, usando fallback de las keys quemadas en los bats...")

    print(f"[*] Inicializando Oráculo con {len(api_key.split(','))} Llave(s).")
    
    try:
        oracle = GeminiOracle(logger=logger)
        
        if not oracle.enabled:
            print("\n❌ RESULTADO: EL ORÁCULO NO PUDO INICIAR (enabled=False). Faltan modelos disponibles.\n")
            return
            
        print("\n✅ Oráculo Iniciado Correctamente.")
        print("📊 Modelos descubiertos en tu cuenta local y cargados dinámicamente:")
        for idx, m in enumerate(oracle.cascade_models):
            print(f"   {idx+1}. {m}")
        print(f"   -> Fallback de Emergencia: {oracle.target_light}")

        print("\n[*] Simulando ingreso de un Trade del Bot (GBPUSD 'BUY' TTM Squeeze)...")
        # Trade Falso
        prompt_prueba = """
        Eres un Analista Cuantitativo.
        El bot detectó una señal técnica:
        - INSTRUMENTO: GBPUSD
        - SEÑAL: BUY (COMPRA)
        - ESTRATEGIA: TTM Squeeze Breakout en periodo de baja volatilidad
        - HORA: 08:30 AM EST (Apertura NY)
        Responde 'YES' si crees que es buena idea o 'NO' seguido de por qué, en JSON: {"decision":"YES","reasoning":"ok"}
        """
        
        print("[*] Enviando Trade a la IA de Google (evaluación con cascada)...")
        decision, razon, modelo_usado = oracle.evaluate_trade("GBPUSD", "BUY", "TTMSqueeze", prompt_prueba)
        
        print("\n" + "="*60)
        print(" 🎯 RESPUESTA RECIBIDA DESDE LOS SERVIDORES DE GOOGLE:")
        print("="*60)
        print(f"Modelo que respondió a la petición: {modelo_usado}")
        print(f"Veredicto IA: {decision}")
        print(f"Razonamiento  : {razon}")
        print("="*60 + "\n")
        
        if "ERROR" in decision or decision == "VETO":
             print("⚠️ La prueba corrió, pero revisa arriba en el Razonamiento si hubo algún bloqueo extraño.")
        else:
             print("🚀 EXITO TOTAL: El código parcheado funciona, maneja bien los modelos libres de 403 y da luz verde sin el error de variable 'time'.")
             
    except Exception as e:
        print(f"\n❌ CRASH LETAL (Aún hay errores de código): {e}")

if __name__ == "__main__":
    main()
