# 🤖 TX3 PRO QUANT BOT - MANUAL DE CAPACIDADES Y OPERABILIDAD

Este documento es el manual técnico y descriptivo completo del ecosistema **TX3 Pro Quant Bot**. Detalla cada una de las inteligencias, filtros y sistemas de seguridad que operan en paralelo para garantizar la integridad institucional del capital gestionado.

---

## 🚀 1. MOTOR DE TRADING CORE: "Dynamic Momentum Pro"

El bot no opera a ciegas. Posee una estrategia base cuantitativa (Algorítmica) que escanea el mercado milisegundo a milisegundo buscando el momento perfecto de ataque asimétrico.

*   **Rastreo Multi-Divisa Simultáneo:** Vigila en tiempo real los principales activos del mundo (`EURUSD`, `GBPUSD`, `USDJPY`), sin latencia humana.
*   **Triple Confirmación Técnica (Modo Francotirador STRICT):**
    1.  **Cruces EMA (20/50):** Detecta los inicios de momentum en el marco de corto plazo (M5).
    2.  **Filtro Direccional (Tendencia H1):** Ningún trade de corto plazo se ejecuta si va en contra de la macrotendencia de 1 Hora.
    3.  **Filtro Antibosquejo (ADX > 18):** Mide la fuerza matemática pura. Si el mercado está en "rango" (ADX bajo), el bot descarta la señal y no opera en lateralidad.
    4.  **Confirmación RSI:** Se asegura de no comprar en techos sobrecomprados ni vender en pisos sobrevendidos.
*   **Gestión del Trade Activo:**
    *   **Smart Trailing Stop:** Al llegar a los +10 pips de beneficio, el bot clava automáticamente el Stop Loss en *Break Even* (Empate). Un trade ganador jamás podrá retroceder y convertirse en rojo. Sube el stop cada 5 pips extras de beneficio.

---

## 🧠 2. CÓRTEX DE INTELIGENCIA ARTIFICIAL (4 CAPAS)

El TX3 Pro es el primer bot de retail que integra 4 modelos de Inteligencia Artificial para razonar el mercado tal y como lo haría un fondo de cobertura en Wall Street.

1.  **Oráculo Principal (Google Gemini 1.5 Pro LLM):** El filtro maestro. Antes de ejecutar cualquier compra técnica, el bot envía la hora, par y fuerza al modelo de Inteligencia Artificial de Google, actuando como el **Chief Investment Officer (CIO)**. Si Gemini detecta que el contexto financiero mundial no es apto (basado en SMC o Price Action), **Veta (Rechaza)** la operación para protegerte.
2.  **News Filter NLP (FinBERT de HuggingFace):** Un modelo de Deep Learning entrenado con Wall Street Journal y Reuters. Escanea titulares y emite una señal de "Pánico" o "Euforia".
3.  **VADER Sentiment (Motor Offline):** Analizador financiero integrado diseñado para correr en el servidor, leyendo pesos emocionales del mercado.
4.  **Machine Learning (Random Forest):** Un modelo matemático predictivo que recuerda la acción de precio pasada y predice a 15 minutos si el precio tiene mayor probabilidad estadística de subir o bajar.

---

## 🛡️ 3. GESTOR DE RIESGO DE GRADO INSTITUCIONAL

Pasar Prop Firms (Firmas de Fondeo) no se trata de ganar mucho, se trata de no perder lo prohibido.

*   **Simulador Estricto $50K (`SIMULATE_50K_CHALLENGE = True`):** El bot ignora mágicamente las ganancias sobreacumuladas en la cuenta. Siempre limitará la pérdida de sus operaciones de riesgo a una base rígida de 50,000 USD (Topando el Drawdown Diario estrictamente a los $2,500 y Global a $5,000). Jamás se sobre-apalancará.
*   **Sizing Fraccional Asimétrico (Kelly Criterion):** Ajusta los lotes (`Volume`) calculando milimétricamente el valor del pip vs el Stop Loss solicitado. Usando `FRAC=0.25`, restringe las apuestas salvajes y preserva el capital.
*   **Escudo de Correlación Automática:** Si el bot entra en `EURUSD` comprado, automáticamente bloquea cualquier trade en `GBPUSD` que pueda inflar el riesgo direccional sobre un mismo billete (dólar).
*   **Killswitch Botón Rojo (Cierre del 85%):** Si el día se torna violento y el bot toca tu $2,125 negativo (El 85% de tu límite diario de pérdida), el sistema aborta. Cierra forzosamente todas las órdenes en mercado y entra en hibernación total, salvando así la cuenta de ser liquidada por la firma de fondeo.
*   **Cierres Forzosos y Protección de Fin de Semana:** El bot no opera cerca de noticias rojas pre-establecidas (Calendario Económico) y expulsa todas las posiciones los Viernes a la tarde obligatoriamente para protegerse de los temidos *Gaps* del fin de semana.

---

## 🎮 4. TELEMETRÍA Y SISTEMAS DE OPERABILIDAD LOCAL

El ecosistema no requiere abrir MetaTrader para saber qué está haciendo. Todo ocurre detrás de escena.

### 🌐 Dashboard Web "Mission Control"
Una interfaz gráfica local estilo "Glassmorphism" con indicadores lumínicos LED.
*   **Balance & Drawdown Tracker:** Muestra en tiempo real qué porcentaje del límite diario o total tienes consumido de forma gráfica y numérica.
*   **Equity Curve Live:** Gráfica matemática generada segundo a segundo mostrando la fluctuación del P&L abierto.
*   **System Health Telemetry:** LEDs que verifican que la conexión al MT5 Broker (**Online**), El Oráculo Gemini (**Consciente**), y el Simulador 50K (**Activo**) están trabajando en orden. Todo directamente en tu navegador.

### 📱 Control Remoto y Alertas vía Telegram
Tu cuenta en tu bolsillo usando la API de Telegram. El Bot te dispara resúmenes interactivos operacionales:
*   `/status` - Solicita un informe de salud sobre el servidor y porcentaje del reto.
*   `/open` - Te chifla qué posiciones están corriendo ahora mismo.
*   `/pause` - Detiene la toma de nuevos trades si presientes un desastre global.
*   `/flat` - **Cierre de Emergencia Humano:** Ordena al bot liquidar y cerrar absolutamente todo de inmediato.
*   `/resume` - Reactiva al robot al campo de batalla.
*   En cada trade aperturado o cerrado, recibirás un extracto completo de los pips ganados o perdidos.

---

## ⚡ 5. ARRANQUE (OPERABILIDAD FLUIDA)

El arranque toma un solo clic gracias al Wrapper del Sistema Operativo (`START_BOT_AND_AI.bat`).
El script se encarga él mismo de levantar las librerías de Python remanentes (`pip`), comprobar los estados offline, inyectar dinámicamente tu **API Key de Gemini** en la memoria del PC e inicializar MetaTrader 5 sin intervención humana repetitiva.

**El TX3 Pro Quant es asincrónico:** Mientras el Oráculo piensa, el Dashboard no se cuelga. Mientras MetaTrader opera, Telegram recibe chats. Todo optimizado para alta frecuencia (HFT Retail).
