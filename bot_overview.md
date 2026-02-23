# 🤖 BOT_OVERVIEW: Anatomía del TX3 Pro Bot

Este documento detalla exhaustivamente todos los módulos, sistemas, lógicas y capas de protección que componen el bot algorítmico **TX3 Pro**, diseñado específicamente para superar exitosamente los retos de fondeo (Prop Firms) de 2 fases.

---

## 🏗️ 1. Arquitectura Central (`main.py`)

El archivo `main.py` actúa como el orquestador maestro (Director de Orquesta). Su loop principal corre ininterrumpidamente y coordina de manera síncrona/asíncrona todos los sistemas.

**Ciclo de Vida del Loop (cada 30 segundos):**
1. Comprueba la conexión constante contra MetaTrader 5.
2. Actualiza el *Phase Tracker* (Rastreador de metas como el Profit Target o los días mínimos).
3. Revisa si son las 17:00 EST para ejecutar el Cierre y Reset Diario (mandando el resumen por Telegram).
4. Actualiza los JSONs en tiempo real que alimentan el servidor del **Dashboard Web**.
5. Mueve dinámicamente el **Trailing Stop** de cualquier posición abierta con profit activo.
6. Evalúa condiciones de **Cierre de Emergencia** si la equidad sufre daños.
7. Evalúa Filtros Globales: Verifica Sesiones Operativas (London/NY) y comprueba el `is_paused` del control remoto.
8. Itera sobre cada símbolo de la "Watchlist" (EURUSD, GBPUSD, etc.):
   - Lanza la estrategia (`ema_cross` / `Machine Learning`).
   - Si la estrategia dice "Compra/Venta", pregunta al **News Filter** (Noticias macroeconómicas + NLP) si es seguro.
   - Pide permiso al **Correlation Shield** para no acumular exposición duplicada.
   - Envía la orden con volumen calculado dinámicamente mediante el **Kelly Criterion**.

---

## 🛡️ 2. Motor de Riesgo y Protecciones (`core/risk_manager.py` & `position_manager.py`)

Esta es la parte más crítica del bot, diseñada explícitamente para sobrevivir y nunca perder la cuenta de fondeo.

### A) Drawdown Management (`risk_manager.py`)
- **Daily Drawdown (5%)**: Calcula tu máxima pérdida permitida basándose en la Equidad del inicio del día (5:00 PM EST).
  - Al 70% del límite manda una alarma por Telegram (Warning).
  - Al 85% ejecuta un **Cierre Killswitch**, liquidando todo automáticamente y suspendiendo el bot por el día.
- **Max Overall Drawdown (10%)**: Mismo esquema de niveles, pero calculado estáticamente sobre el balance inicial de los $50,000.

### B) Fractional Kelly Sizing (`position_manager.py`)
El bot no usa volumen aleatorio o fijo. La IA calcula la probabilidad de ganar de un *setup* particular y luego el `Kelly Criterion` matemático dictamina qué porcentaje del capital debe arriesgarse:
- Si la probabilidad es **alta (>75%)**: Arriesga `1.2% x KELLY_FRACTION (0.25) = 0.30%` del capital.
- Si la probabilidad es **dudosa (<55%)**: Arriesga `0.2% x KELLY_FRACTION (0.25) = 0.05%` del capital para evitar pérdidas mayores.

### C) Escudo Anti-Correlación (`check_correlation_shield`)
Impide que el bot abra una compra en EUR/USD y otra compra en GBP/USD al mismo tiempo si considera que esto dobla la exposición al Dólar (Riesgo en cascada).

---

## 🧠 3. Estrategias y ML (`strategy/` y `scripts/train_ml_model.py`)

El bot decide sus entradas a partir de un sistema híbrido que cruza análisis técnico de alta escuela y predicción no-lineal por Inteligencia Artificial offline.

- **Estrategia EMA Cross (`ema_cross.py`)**: Analiza la relación, distancia y volatilidad (Pips de expansión) entre las medias móviles exponenciales de 20 y 50 períodos de velas de 5 minutos, buscando estirar tendencias largas sin atraparse en rangos aburridos (verificando métricas como `ADX` u osciladores parecidos a definir según filtro `STRICT` en `settings.py`).
- **Machine Learning Trainer**: El script de entrenamiento descarga hasta 10,000 velas de antigüedad del Broker. Pre-procesa *features* avanzadas como: 
  - Día de la semana.
  - Horario operativo.
  - Distancia de EMAs en pips (`ema_dist`).
  - Cálculo Vectorial del RSI.
  - Diferencial de retornos intertemporales de 3 barras traseras.
  Con estos datos, la librería Scikit-Learn entrena un algoritmo *Random Forest (Bosque Aleatorio de 100 Decision Trees)* para decidir cuál es el *Edge* probabilístico y escupe un archivo llamado **Cerebro** (`rf_model.pkl`).

---

## 📰 4. Filtro Avanzado de Noticias e IA Fundamental (`core/news_filter.py` & `core/ai_sentiment.py`)

El bot proactivamente examina el calendario económico de *ForexFactory* para cuidarte de barridas de SL manipuladas:
- Detecta qué moneda reportará una Noticia de "Alto Impacto" (Rojos) en las próximas horas.
- Apaga transitoriamente los pares asociados **30 minutos antes y 15 minutos después**.

**Análisis de Sentimiento (FinBERT):**
Si le provees un *HUGGINGFACE_TOKEN*, el bot conectará su núcleo fundamental a un modelo FinBERT (procesamiento NLP financiero). FinBERT escaneará los artículos e indexará si la noticia es "Bullish" (A favor del USD) o "Bearish" (En Contra), permitiéndole discernir ruidos del mercado o sumarle puntos extra a la probabilidad en el análisis técnico.

---

## 📱 5. Telegram Remote Panel (`utils/telegram_commands.py`)

El bot nunca duerme, y siempre está en tu teléfono. Levanta un servidor asíncrono invisible (*Polling Daemon Thread*) que escucha exclusivametne la ID Privada de tu cuenta de Telegram:
- **`/status`:** Panel con balance, equidad, profit abierto y uptime del VPS.
- **`/profit`:** Resumen de crecimiento de la cuenta y objetivos fondeados.
- **`/positions`:** Listado exhaustivo de lotes abiertos + profit de cada ticket actual.
- **`/risk`:** Visualización con barra de nivel (`[🟥🟥🟥⬜⬜] 30%`) del drawdown y salud del reto.
- **`/pause` y `/resume`:** Comando Killswitch. Detiene al bot abriendo posiciones (Útil si te fuiste de fiesta y crees que habrá bajo volumen por la tarde).
- **`/flat`:** Cierra todo abruptamente (Cierre de botón rojo).

---

## 🌐 6. Mission Control Web Dashboard (`dashboard/app.py` & `dashboard/templates/index.html`)

Alojado por defecto en `http://localhost:5050`, el bot levanta usando la librería en Python Flask, un WebSocket servidor con arquitectura frontend `TailwindCSS` y Javascript `Chart.js` que se comunica a 5,000 milisegundos de actualización. Pudiendo ver visualmente tu:
1. Gráfico interactivo en vivo del *Equitiy/Account Balance History*.
2. Posiciones mostradas en formato de Tabla Financiera.
3. Consola transparente para observar cada Log y evento del backend desde una página web sin abrir el CMD de Windows.
4. Estado del bot marcando `RUNNING`/`PAUSED` y `DEMO`/`LIVE`.

---

## ⚙️ 7. Settings Centralizados (`config/settings.py`)

Literalmente un "Cerebro Manual" paramétrico para configurar todas las llaves del bot en un solo archivo, pre-reglado para desafíos de $50,000 USD. Contiene:
- Criterios del Reto: Profit targets (`FASE1_PROFIT_TARGET`) e inflexibles Drawdowns Max.
- Criterios del Bot: `KELLY_FRACTION`, Símbolos, Pip Ranges para Stop Loss/Take Profit.
- Criterios de Horario: Qué horas de overlap entre London & NY operar.

El **TX3 Pro Bot** no solo adivina a dónde va una barrita verde o roja; procesa datos Macro y Cuantitativos en milisegundos y respeta la Sagrada Ley del Trader: _Nunca dejes que el Drawdown toque el límite_.
