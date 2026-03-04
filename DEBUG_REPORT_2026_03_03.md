# 🐛 DEBUG REPORT: Auditoría y Parches Críticos (Marzo 2026)
=========================================================

Este documento funciona como una bitácora forense de todos los fallos, *"Bugs"* y cuellos de botella algorítmicos que se descubrieron, auditaron y solucionaron de raíz en el día de hoy, estabilizando el TX3 Pro Bot a nivel institucional.

---

## 🛑 1. El Falso Positivo del Oráculo IA (Veto Bypass Bug)
**El Problema:**
El comando `/test_veto` demostró que el Bot estaba "Aprobando" automáticamente operaciones estúpidas o suicidas. Al auditar la telemetría, el dashboard en Telegram arrojaba un límite `0/0` en herramientas clave como `gemini-2.0-flash` y `gemini-2.5-pro`. Debido a las políticas ocultas del Free Tier de Google AI Studio, estos modelos estaban capados o bloqueados regionalmente. Ante la caída de la API, el bot aplicaba el "Quant Bypass" (Fallback matemático) y ejecutaba la orden ciegamente sin análisis cognitivo.

**La Solución:**
1. **Re-enrutamiento de Modelos (Smart Tiering):** Modificamos el descubridor de redes neuronales (`llm_oracle.py`) para ignorar los modelos Pro de pago y anclar la prioridad Absoluta al modelo **`gemini-2.5-flash`** (El único con velocidad institucional liberado en la capa gratuita).
2. **Brute-Force Empírico:** Se programó el script `test_limit.py`, para estresar los flujos de Google y descubrir el límite silenciado y real de la API. Comprobamos que el Request Per Minute (RPM) estaba castigado a **5 disparos por minuto**, no 15.
3. **Parchado del Token Bucket:** Se actualizaron los rate-limiters dentro del bot de `15 RPM` a `5 RPM`. Esto obliga al bot a "hacer la fila" ordenadamente y jamás recibir un nuevo ban `429 Error` de Google por saltar la cuota de la sesión.

---

## 🛑 2. Error Semántico de Librería (SMC Scanner Breakdown)
**El Problema:**
El motor *Smart Money Concepts* reventaba los logs de consola intentando analizar bloques de órdenes (Order Blocks/Liquidity Voids), causando que los filtros técnicos en la generación de la señal tiraran un Traceback de Python que truncaba toda la evaluación de velas. El fallo se debía a que se estaba llamando la función de escaneo sin proveerle explícitamente el argumento mandatorio de `timeframe`.

**La Solución:**
Se reescribió la inyección de dependencias en `smc_scanner.py` forzando el paso unificado de la variable de entorno `BotConfig.DEFAULT_TIMEFRAME (M5)` como argumento seguro de fallback, sellando el bucle de interrupciones.

---

## 🛑 3. Glitch Gráfico de Telemetría al Bootear (Dashboard UI Bug)
**El Problema:**
Apenas se activaba el bot, el comando de Telegram `/quota` y el log principal indicaban falsamente que a la IA apenas le quedaban `20 disparos` diarios en la capa Crítica, en lugar de los `1,500` liberados, lo cual causaba sustos y obligaba al usuario a creer que el bot fallaría en breve.

**La Solución:**
Refactorizamos los bucles de literal mapping en la clase del `__init__` (`llm_oracle.py`), empatando los Fallback Buckets bases con `1500 Requests Per Day` temporales justo antes de que el servidor contacte a Google para alinear métricas. Eliminando el fantasma y bug visual para siempre.

---

## 🛑 4. Retardo de Servidor y "Thrashing" Computacional (Frontend DOM Lag)
**El Problema:**
El Dashboard Web (Mission Control) consumía montones de CPU en navegadores de Chrome al tener el Bot abierto. La tabla central que pinta las transacciones se *"auto-destruía y reconstruía"* desde cero a nivel de DOM HTML en cada microsegundo cada vez que llegaba una actualización por WebSocket, sin importar si los datos seguían idénticos.

**La Solución:**
1. Arquitectura estilo "React". Se construyó un Hash de datos en MD/JSON puro en Javascript. El frontend en `index.html` ahora compara instantáneamente el Hash pasado vs el actual: **Si no difieren las transacciones, la tabla se bloquea, ignorando Renderizados (Layout Thrashing)**.
2. Aceleración a 2 Segundos: Al quitarle carga gráfica a la computadora, pudimos reducir el Loop asíncrono en `settings.py` (De 10 segundos) a unos increíbles **2.0 segundos de reacción (*Tick Rate*)**, volviendo la vista a MT5 extremadamente sensitiva sin lag guebernamental.

---

## 🛑 5. Ausencia de "Killzones" para Fondeos Estrictos (Session Risks)
**El Problema:**
El bot estaba permitiendo (Técnicamente) operaciones lentas de "Spreads y Rango" durante horarios nocturnos muertos como la sesión de Asia o la transición al fin de semana, arriesgando holding costs en la Prueba de Fondeo.

**La Solución:**
Se programaron e insertaron 2 candados absolutos (`RESTRICT_TO_LONDON_NY` y `FRIDAY_FLAT_HOUR` en `settings.py` integrados en el código Core del Objeto). Si hoy es viernes y dan las 12 PM mediodía, el bot manda Killswitch y cierra el grifo automáticamente hasta la apertura del domingo. Ignorando a perpetuidad las madrugadas poco volátiles del Yen/Aussie.

---

## 🛑 6. Desbordamiento Silencioso por Límites de API Personalizados (Hard RPD Quota)
**El Problema:**
Al escanear el panel de usuario directamente en AI Studio de Google, descubrimos que las nuevas llaves tenían aplicada una penalización ultra restrictiva en capa Free: el límite diario de `gemini-2.5-flash` era de tan solo **20 Requests Per Day (RPD)**, y no las típicas 1,500. El bot, asumiendo su tanque normal de gasolina, no gestionaba el ahogo inminente e inevitable del trade #21.

**La Solución:**
Actualizamos los valores críticos en el núcleo central (`llm_oracle.py`). Al endurecer el Token Bucket local `rpd_limit` en estricto 20, aseguramos que el Bot sepa detener la Inteligencia superior y activar transparentemente el *Quant Bypass (Red de Trading Matemática)* o IAs más simples inmediatamente al gastar esos 20 tickets únicos, evitando crasheos 429 durante el día.

---

## 🛑 7. Punto Único de Fallo en IA y Sub-utilización (Dynamic AI Cascade Waterfall)
**El Problema:**
El script revelaba que Google habilita aleatoriamente excelentes versiones híbridas temporales (Gemini 3.0, Flash-Lites) dependiendo de la cuenta, pero nuestro bot mantenía una lista programada "Hard-Coded" inamovible (Tier 1 vs Tier 2), desaprovechando estas mejoras masivas de latencia gratuita si el Tier 2 principal caía.

**La Solución:**
Desarrollamos una Arquitectura de "Cascada Inteligente". Acabamos con las posiciones fijas y programamos al Core para autodetectar los modelos desde los servidores de Google al iniciar el '.bat'. Construye dinámicamente una cadena de priorización: 
**Prioridad (Tier Oro):** Gemini 3.0 / 2.5 Normales.
**Respaldo Secundario (Tier Plata):**  Versiones `Flash-Lite`.
**Caída Libre (Tier Cobre):** Modelos `Gemma-3` equilibrados (Con cupón infinito de 14.4K RPD).
Si uno se queda sin cuota, salta silenciosamente al siguiente sin perder el Trade en MetaTrader. 

---

## 🛑 8. Fallo de Referencia en el Auto-Diagnóstico de Arranque (Crash Dr. Quant)
**El Problema:**
El Bot fallaba su rigurosa Auto-Prueba de inicio deteniéndose con un temible código: `'GeminiOracle' object has no attribute 'model_light'`. Causado justamente a raíz del cambio de Arquitectura en Cascada, ya que las revisiones diagnósticas de salud médica (el bot leyendo MT5) buscaban variables estáticas de la generación pasada de código que ya habían sido borradas y modernizadas.

**La Solución:**
Reprogramamos los módulos `evaluate_system_health` y `ask_oracle` retirando cualquier mención obsoleta de llamadas `model_light`. Ahora apuntan a la constante `target_light` encastrada armoniosamente con el array de strings de la Cascada Inteligente. Auto-Test completamente verde y en línea.
