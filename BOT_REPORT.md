# 📊 TX3 PRO QUANT BOT - Informe Técnico Completo (Actualizado)

Este documento representa un análisis exhaustivo y estructurado de la arquitectura técnica, las estrategias operativas y los sistemas de gestión de riesgo implementados en el **TX3 Pro Quant Bot**. Su propósito es servir como documentación oficial del nivel institucional del sistema.

---

## 1. ⚙️ ARQUITECTURA DEL SISTEMA Y TECNOLOGÍAS CORE

El bot ha sido refactorizado desde un sistema básico de seguimiento de tendencias ("Trend Hunter") hacia una infraestructura Quant de alta frecuencia e Inteligencia Artificial modular.

*   **Lenguaje Base:** Python 3.10+
*   **Conectividad Broker:** API Nativa de MetaTrader 5 (Ejecución de latencia ultra baja en mercado real/demo).
*   **Paradigma de Diseño:** Programación Orientada a Objetos (OOP) con módulos independientes y asíncronos.
*   **Persistencia de Estado:** Sistema inteligente de serialización JSON (`bot_state.json`) que permite recuperaciones ante fallos eléctricos o reinicios de VPS sin perder noción del Profit Diario ni de los Drawdowns acumulados.

---

## 2. 🧠 INTELIGENCIA ARTIFICIAL: EL CÓRTEX DE 4 CAPAS

El mayor salto tecnológico del TX3 Pro es su capacidad cognitiva para interpretar el contexto Macro y Técnico del mercado a través de 4 motores de IA corriendo en paralelo:

1.  **Google Gemini 1.5 Pro (CIO Oracle):**
    *   **Función:** Actúa como el *Chief Investment Officer*. Es el filtro final mediante la API de Google Generative AI.
    *   **Mecánica:** Antes de ejecutar un trade detectado por los algoritmos técnicos, el bot envía la hora, par, sentido de la orden y fuerza (ADX) a Gemini. Evaluando conceptos avanzados institucionales (Smart Money Concepts, ICT, Price Action), el Oráculo decide si el contexto es seguro.
    *   **Poder de Veto:** Puede responder `JSON { "decision": "REJECTED" }` y abortar el trade si detecta trampas de liquidez institucionales o condiciones desfavorables.
2.  **Machine Learning (Random Forest Classifier):**
    *   **Función:** Análisis predictivo puro de la acción de precio.
    *   **Mecánica:** Entrenado con millones de barras históricas (Open, High, Low, Close, Tick Volume) para emitir una probabilidad de éxito a corto plazo (15m). El modelo aprende continuamente y se reentrena automáticamente los fines de semana.
3.  **HuggingFace FinBERT (Deep Learning NLP):**
    *   **Función:** Analista de Sentimiento de Noticias Financieras.
    *   **Mecánica:** Descarga titulares económicos en tiempo real (ej. Myfxbook/ForexFactory) y los clasifica como *Positivos*, *Negativos* o *Neutrales* utilizando procesamiento de lenguaje natural especializado en finanzas.
4.  **VADER Sentiment (Motor Offline):**
    *   **Función:** Sistema de Respaldo Ponderado.
    *   **Mecánica:** Si la API en la nube falla, este motor ligero ejecutado directamente en el procesador del VPS clasifica eventos noticiosos analizando léxico financiero específico en fracciones de segundo.

---

## 3. 📉 ESTRATEGIA MATEMÁTICA: DYNAMIC MOMENTUM PRO

Cuando la Inteligencia Artificial aprueba operar, el motor cuantitativo base toma el control técnico.

*   **Multidivisa Simultáneo:** Escaneo en paralelo de una `Watchlist` diversificada (ej. EURUSD, GBPUSD, USDJPY).
*   **Filtro Direccional Macro (H1):** Bloqueo anti-retrocesos. Nunca comprará en temporalidades menores (M5) si la tendencia en 1 Hora es bajista.
*   **Doble Confirmación Corto Plazo (M5):**
    *   Cruces de Medias Móviles Exponenciales (EMA 20 y EMA 50).
    *   Validación de momento con el Indice de Fuerza Relativa (RSI).
*   **Escudo Antirango (Modo STRICT):** Utilizando el indicador ADX, el bot exige una fuerza direccional superior al nivel 18. Si el mercado está "plano" (Rango de consolidación), ignora todas las señales técnicas.

---

## 4. 🛡️ GESTOR DE RIESGO: EL "SANTO GRIAL" PROP FIRM

La principal causa de fracaso en firmas de fondeo es el incumplimiento de Drawdown. El `RiskManager` central del TX3 Pro está diseñado para ser matemáticamente infalible.

*   **Simulador Estricto $50K (`SIMULATE_50K_CHALLENGE`):** Un feature exclusivo que desvincula el riesgo del balance real del broker. Si tienes $97,000 en la cuenta, el bot actuará matemáticamente como si sólo tuviera $50,000 fijos, manteniendo los límites diarios ($2,500) y totales ($5,000) intactos sin inflar los lotajes.
*   **Position Sizing (Kelly Criterion Fraccional):** Asignación inteligente de lotaje asimétrico. Usando la fórmula de Kelly al 25% (`FRAC=0.25`), el bot arriesga un porcentaje estricto (ej. 0.25% - 0.5%) y calcula los Lotes exactos basándose en el valor real del Pip y los dígitos del broker en tiempo real.
*   **Escudo de Correlación:** Previene el suicidio de la cuenta por sobre-exposición. Si compra Dólares (ej. USDJPY), el bot bloquea automáticamente algoritmos que intenten vender otras monedas contra el Dólar simultáneamente.
*   **Emergency Killswitch al 85%:** Si una serie de eventos anómalos o *Black Swans* llevan el flotante diario cerca del 4% (85% de tu margen de 5%), el bot presiona el "Botón Rojo": Liqiuda todas las operaciones mediante `emergency_close_all()` y se apaga hasta el día siguiente.
*   **Smart Trailing Stop y Mantenimiento:** Asegura los pips de ganancias moviendo el Stop Loss a *Break Even* tras sumar 10 pips a favor. Adicionalmente, cuenta con un cierre forzoso los días Viernes para evitar gaps del fin de semana.

---

## 5. 🕹️ TELEMETRÍA, DASHBOARD Y CONTROL (C4I)

No requieres abrir MetaTrader 5 en tu computadora para gestionar y observar al bot.

*   **Mission Control Dashboard (Web App):**
    *   Interfaz moderna (Glassmorphism, Dark Mode).
    *   **System Health Telemetry:** Leds en directo indicando la conexión exitosa del API de MT5, el estatus del CIO Oracle (Gemini), estado del motor NLP de noticias, y si el Simulador 50K está activo.
    *   Representación en vivo del Equity Curve y de los metros de progreso hacia el Profit Target y el Drawdown Diario consumido.
    *   Lista instantánea de las operaciones vivas y log de eventos del sistema.
*   **Comando Táctico por Telegram:**
    El módulo `telegram_commands.py` permite manipular la lógica del sistema operando desde tu celular, en cualquier parte del mundo:
    *   `/status` - Resumen de salud.
    *   `/open` - P&L de las órdenes actuales flotando.
    *   `/flat` - **Liquidación Total Instantánea** a mercado.
    *   `/pause` y `/resume` - Para inhibir entradas antes de eventos mundiales no previstos (ej. Guerras, Cadenas Nacionales).

---

## 6. 🏁 CONCLUSIÓN TÉCNICA

El **TX3 Pro Quant Bot** ha evolucionado más allá de un experto asesor convencional. Es un conjunto de algoritmos superpuestos de control estocástico, Inteligencia Artificial y gestión de riesgos pasiva. 

Su directriz fundamental no es buscar el "High Yield" rápido y riesgoso, sino domar la estadística de largo plazo con preservación agresiva de capital, transformando la tarea de superar una Prop Firm de 50K en un proceso calculado, monitorizable y matemáticamente seguro.
