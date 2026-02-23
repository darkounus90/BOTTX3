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

## 2️⃣ Arquitectura del Proyecto

El bot está diseñado con un enfoque modular e institucional, separando la lógica para mayor mantenibilidad:

- `main.py`: Punto de entrada principal. Orquesta los ciclos de trading, hilos de ejecución secundaria, mutación genética y dashboard en tiempo real.
- `config/settings.py`: Archivo maestro de configuración. Aquí se centralizan los parámetros de riesgo (`KELLY_FRACTION`), filtros institucionales, llaves secretas y metas de negocio. Ningún número está _hardcodeado_ en los scripts.
- `core/`: Cerebro operativo avanzado. Contiene:
  - `risk_manager.py` (Gestión estricta de límites de Prop Firms).
  - `position_manager.py` (Cálculo dinámico matemático usando Kelly Criterion).
  - `smc_scanner.py` (Detector de Order Blocks y FVG - Liquidez bancaria).
  - `llm_oracle.py` (Conciencia AI actuando como CIO analizando MTF vía Gemini).
  - `portfolio_manager.py` (Rebalanceo dinámico de riesgo por volatilidad relativa).
- `strategy/`: Estrategias de trading. Contiene matemática (`ema_cross.py`) y Reinforcement Learning (`q_learning_agent.py` para optimización autónoma).
- `dashboard/`: Sistema web con Flask y WebSockets para monitorear el PnL.
- `utils/`: Herramientas auxiliares (`telegram_commands.py` para control remoto, logs de sistema, conector MT5).

---

## 2️⃣ Instalación y Arranque Rápido (1-Click)

La forma más sencilla y automatizada de ejecutar el bot, instalar sus dependencias, y preparar su "Cerebro de Inteligencia Artificial" es usar el script de arranque incluido.

1. Abre tu carpeta del bot en Windows o tu VPS.
2. Dale doble clic al archivo **`START_BOT_AND_AI.bat`** (o ejecútalo desde tu consola PowerShell con `.\START_BOT_AND_AI.bat`).

Este script Inteligente se encargará automáticamente de:
- Verificar e instalar las librerías necesarias de Python.
- Descargar el historial de MetaTrader y entrenar la memoria algorítmica (Machine Learning).
- Iniciar el Bot en Fase 1 y levantar el servidor del Dashboard.

> Si ves un error como `ModuleNotFoundError: No module named 'MetaTrader5'`, asegúrate de tener Python instalado correctamente en tu Windows y de haber marcado la casilla "Add to PATH" durante la instalación.

---

## 3️⃣ Configuración Avanzada (Tokens e IA)

Si quieres usar el **Cerebro Oráculo de Gemini** (CIO Institucional) y las notificaciones remotas de Telegram, debes configurar variables de entorno o editar tu script de inicio `.bat`/`.sh`:

```bat
:: Configura tus credenciales aquí:
set TELEGRAM_BOT_TOKEN="tu_token_aqui"
set TELEGRAM_CHAT_ID="tu_chat_id_aqui"
set DASHBOARD_SECRET="tu_contraseña_web"
set GEMINI_API_KEY="tu_token_google_gemini_aqui"
```

> **Nota sobre el Oráculo AI**: Si no configuras el `GEMINI_API_KEY`, el oráculo CIO se desactivará automáticamente y el bot operará 100% en Modo Quant Matemático puro sin validación narrativa.

**Opcional:** Edita `config/settings.py` para encender o apagar módulos institucionales como `SMC_ENABLED` o el Agente de Aprendizaje Reforzado `Q_LEARNING_ENABLED`.

---

## 4️⃣ Ejecución Manual del Bot

Si prefieres la terminal en lugar del script `.bat`, el bot tiene 3 modos principales. Elige el que corresponda a tu fase actual:

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

## 6️⃣ Control Remoto (Telegram)

Puedes enviar comandos desde Telegram directamente a tu bot para consultar su estado en tiempo real. 

### Comandos Soportados:
-   `/status` → Estado general (Balance, Equity, P&L, etc.)
-   `/positions` → Lista de operaciones abiertas interactiva
-   `/profit` → Resumen de ganancias y equidad flotante
-   `/risk` → Vista gráfica del Drawdown Diario y Total con advertencias
-   `/ask <pregunta>` 🧠 → Habla directamente con el Oráculo AI en vivo (Gemini)
-   `/report` 📝 → Genera un análisis narrativo del estado de la cuenta por el CIO
-   `/pause` ⏸️ → Pausa temporalmente el escaneo de nuevas oportunidades
-   `/resume` ▶️ → Reanuda la operativa normal del bot
-   `/flat` 🧹 → Cierra de emergencia todas las posiciones a precio de mercado
-   `/help` ℹ️ → Menú de todos los comandos

*Para que funcione el control remoto, debes asegurarte de configurar las variables `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` en el sistema.*

---

## 7️⃣ Solución de Problemas Comunes

### ❌ `ModuleNotFoundError: No module named 'MetaTrader5'`
-   **Causa**: No has instalado las librerías o estás intentando correr el bot en Mac/Linux nativo.
-   **Solución**: Ejecuta el archivo `START_BOT_AND_AI.bat` en **Windows**.

### ❌ `Fallo al conectar a MT5`
-   **Causa**: La terminal MT5 no está abierta o no coincide la cuenta.
-   **Solución**: Abre la terminal MT5 visualmente, loguéate, y asegúrate de que el botón superior "Auto Trading" esté activado.

### ❌ Error descargando datos de Machine Learning (`❌ No hay datos para EURUSD`)
-   **Causa**: El mercado está cerrado cerrado por fin de semana, o en tu broker la divisa se llama distinto (Ej. EURUSD.pro).
-   **Solución**: Si es fin de semana el bot creará automáticamente un cerebro de emergencia para no detenerse. Si falla entre semana, edita `scripts/train_ml_model.py` para usar el sufijo correcto de tu broker.

### ❌ El bot no abre operaciones
-   **Causa**: Puede ser por horario (fuera de sesión), spread alto, o noticias.
-   **Solución**: Revisa los logs en el Dashboard o la terminal. Si dice "Mercado cerrado" o "Spread alto", es comportamiento normal de protección de capital.

---

## 📋 Resumen de Comandos Rápidas

| Acción | Comando |
| :--- | :--- |
| **Arranque Inteligente** | `.\START_BOT_AND_AI.bat` |
| **Simular (Fase 1)** | `python main.py --phase 1 --dry-run` |
| **Re-entrenar IA** | `python scripts/train_ml_model.py` |
| **Telegram Ayuda** | Enviar `/help` al bot en Telegram |
