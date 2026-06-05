@echo off
echo ==========================================================
echo    INSTALADOR DE PYTORCH + CUDA PARA RTX 5070
echo ==========================================================
echo.
echo Detectando entorno virtual (venv312)...
if not exist "venv312\Scripts\python.exe" (
    echo [ERROR] No se encontro venv312. Ejecuta START_BOT_AND_AI.bat una vez primero.
    pause
    exit /b
)

echo [1/2] Desinstalando versiones previas de torch (por si acaso)...
venv312\Scripts\pip.exe uninstall -y torch torchvision torchaudio

echo [2/2] Instalando PyTorch 2.3.1 con soporte CUDA 12.1 (Aceleracion GPU)...
echo Esto descargara aproximadamente 2.5 GB. Por favor, espera...
venv312\Scripts\pip.exe install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo.
echo ✅ Instalacion Completada. 
echo Tu laboratorio local ahora tiene soporte Deep Learning por Hardware.
pause
