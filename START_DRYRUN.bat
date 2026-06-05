@echo off
echo ==========================================================
echo    🧪 TX3 PRO BOT - MODO PRUEBA (DRY RUN)
echo    ⚠️  NO SE EJECUTARAN ORDENES REALES
echo ==========================================================
echo.
echo [1/3] Verificando e Instalando Librerias de Inteligencia Artificial...
pip install -r requirements.txt
echo.

echo [2/3] Verificando Memoria de Machine Learning...
if not exist "data\rf_model_NAS100.pkl" (
    echo    ! El Cerebro IA es nuevo y necesita ser entrenado por primera vez.
    echo    - Ejecutando el Scanner y Entrenador Espacial - Esto tardara 1-2 minutos...
    python scripts\train_ml_model.py
) else (
    echo    ✅ El Cerebro IA ya esta cargado y en linea.
)
echo.

:: Credenciales (mismas que produccion)
if exist "secrets.bat" (
    echo [i] Cargando credenciales seguras desde secrets.bat...
    call secrets.bat
) else (
    echo [WARNING] No se encontro secrets.bat. Se usaran variables de entorno del sistema.
)

echo [3/3] 🧪 Arrancando Bot en MODO PRUEBA (DRY RUN) - Fase 1...
echo    ✅ El bot analizara el mercado en tiempo real
echo    ✅ La IA evaluara senales normalmente
echo    ✅ El Dashboard funcionara con datos reales
echo    ❌ NO se abriran operaciones reales
echo ==========================================================
python main.py --phase 1 --dry-run
pause
