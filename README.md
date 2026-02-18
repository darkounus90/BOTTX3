# 🤖 TX3 Pro Bot $50K - Guía de Uso Completa

¡Bienvenido a tu bot profesional para el **TX3 Funding Challenge**! Sigue estos pasos exactos para ponerlo en marcha.

> ⚠️ **REQUISITO CRÍTICO**: Este bot utiliza la librería oficial `MetaTrader5` de Python, que **SOLO FUNCIONA EN WINDOWS**.
> Si estás en **Mac** o **Linux**, necesitas ejecutar este bot en:
> 1. Una Máquina Virtual con Windows (Parallels, VMware).
> 2. Un VPS con Windows (recomendado para trading real 24/7).
> 3. Boot Camp (en Mac Intel).

---

## 1️⃣ Preparación del Entorno (Windows)

1.  **Instalar Python 3.10 o superior**:
    -   Descarga desde [python.org](https://www.python.org/downloads/windows/).
    -   Al instalar, marca la casilla **"Add Python to PATH"**.

2.  **Instalar Terminal MetaTrader 5**:
    -   Descarga e instala MT5 desde [TX3 Funding](https://tx3funding.com) o tu broker.
    -   Inicia sesión con tu cuenta de trading.
    -   En MT5, ve a **Herramientas > Opciones > Asesores Expertos (Expert Advisors)** y marca:
        -   ✅ Permitir el trading algorítmico.
        -   ✅ Permitir importación de DLL.

---

## 2️⃣ Instalación del Bot

Abre una terminal (PowerShell o CMD) en la carpeta del bot y ejecuta:

```bash
# 1. Crear entorno virtual (opcional pero recomendado)
python -m venv venv
.\venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt
```

> Si ves un error como `ModuleNotFoundError: No module named 'MetaTrader5'`, significa que no se instalaron las dependencias o estás intentando instalarlo en Mac/Linux (donde no está disponible).

---

## 3️⃣ Configuración (Opcional)

Si quieres notificaciones en Telegram, configura las variables de entorno antes de ejecutar el bot.

**En PowerShell:**
```powershell
$env:TELEGRAM_BOT_TOKEN="tu_token_aqui"
$env:TELEGRAM_CHAT_ID="tu_chat_id_aqui"
```

**Opcional:** Edita `config/settings.py` para ajustar parámetros como lotaje, riesgo, u horarios, aunque los valores por defecto están optimizados para el **Challenge de $50k**.

---

## 4️⃣ Ejecución del Bot

El bot tiene 3 modos principales. Elige el que corresponda a tu fase actual:

### 🔵 FASE 1 (Objetivo 10% = $5,000)
```bash
python main.py --phase 1
```

### 🟣 FASE 2 (Objetivo 5% = $2,500)
```bash
python main.py --phase 2
```

### 🧪 MODO SIMULACIÓN (DRY RUN)
Prueba que todo conecte sin abrir operaciones reales:
```bash
python main.py --phase 1 --dry-run
```

Si todo está bien, verás un mensaje como:
`✅ CONECTADO A METATRADER 5` y `🌐 Dashboard iniciando en http://0.0.0.0:5050`

---

## 5️⃣ Monitoreo Web (Dashboard)

Una vez que el bot esté corriendo, abre tu navegador y ve a:

**👉 [http://localhost:5050](http://localhost:5050)**

Verás un panel de control con:
-   Balance y Equity en tiempo real.
-   Gráfico de Drawdown Diario y Total.
-   Lista de posiciones abiertas.
-   Logs en vivo de lo que hace el bot.

---

## 6️⃣ Solución de Problemas Comunes

### ❌ `ModuleNotFoundError: No module named 'MetaTrader5'`
-   **Causa**: No has instalado las librerías o estás en Mac/Linux.
-   **Solución**: Ejecuta `pip install -r requirements.txt` en **Windows**.

### ❌ `Fallo al conectar a MT5`
-   **Causa**: La terminal MT5 no está abierta o no coincide la cuenta.
-   **Solución**: Abre la terminal MT5 visualmente y asegúrate de que el log diga "Connected".

### ❌ El bot no abre operaciones
-   **Causa**: Puede ser por horario (fuera de sesión), spread alto, o noticias.
-   **Solución**: Revisa los logs en el Dashboard o la terminal. Si dice "Mercado cerrado" o "Spread alto", es comportamiento normal de protección.

---

## 📋 Resumen de Comandos

| Acción | Comando |
| :--- | :--- |
| **Instalar** | `pip install -r requirements.txt` |
| **Fase 1** | `python main.py --phase 1` |
| **Fase 2** | `python main.py --phase 2` |
| **Simular** | `python main.py --phase 1 --dry-run` |
