# Revisión: ¿por qué el bot nunca gana?

Revisión del código en vivo (`main.py` → `TTMSqueezeStrategy` + `AIBrainStrategy` en EURUSD) contra
lo que se validó en los backtests. Resumen: **el bot que corría en vivo no era el bot que se backtesteó**,
y además tenía fallos que lo dejaban sin operar o sin protección.

## 1. La gestión de salidas destruía el Risk:Reward (causa principal)

El backtest de TTM Squeeze (`scripts/strategy_backtester.py`) simula **SL y TP fijos** (SL 1.5 ATR / mín. 15 pips,
TP 4 ATR / mín. 30 pips). En vivo, `core/trailing_stop.py` cambiaba todo:

| Regla en vivo | Efecto en EURUSD M15 (ATR ≈ 7 pips) |
|---|---|
| Trailing desde +8 pips, SL a 4 pips del precio | Cualquier retroceso de 4 pips cierra el trade |
| Break-even (+1 pip) al llegar a +1×ATR | Se activa a ~+7 pips |
| Cierre parcial 50% en 1R | Raramente llega (el trailing cierra antes) |
| Oráculo IA puede "asfixiar" el SL a 7 pips | Cierres por opinión de un LLM |

Resultado aproximado por operación (incluyendo ~1.5 pips de spread + comisión):

- **Pérdida:** −15 a −20 pips completos.
- **Ganancia típica:** +1 a +8 pips (el TP de 30–40 pips casi nunca se alcanza).
- Win rate necesario para no perder: **≈ 75–80 %**. Con SL/TP fijos 15/30: **≈ 37 %**.

Una estrategia de *breakout* gana con las pocas operaciones que corren mucho; cortarlas a +4 pips elimina justo
esa ventaja. **Arreglo:** `TRAILING_STOP_ENABLED = False` (vuelve a SL/TP fijos, igual que el backtest).
Si se quiere trailing, primero hay que simularlo en el backtester y demostrar que mejora el Profit Factor.

## 2. El cierre de emergencia no existía

`main.py` y el comando `/flat` de Telegram llamaban a `RiskManager.emergency_close_all()`, pero el método
había sido borrado (el archivo decía *"omitidos aquí por brevedad, copiarlos sin cambios"*). Consecuencias:

- Al tocar el 95 % del drawdown diario/total → `AttributeError`, **no se cerraba nada**.
- Cierre de viernes 15:00 NY → error en cada vuelta del loop, las posiciones pasaban el fin de semana.

**Arreglo:** implementado `emergency_close_all()` (cierra solo posiciones con el `MAGIC_NUMBER`, con reintentos).

## 3. Un fallo de la API de noticias bloqueaba el día entero

Si la primera petición del día a ForexFactory fallaba (timeout de 3 s o el 429 de Cloudflare que ya se vio en
el historial), `api_failed_today` quedaba en `True` y **ninguna señal se ejecutaba hasta el día siguiente**.

**Arreglo:** se sigue bloqueando mientras la API falle, pero se reintenta cada `NEWS_API_RETRY_MINUTES` (10 min)
y solo se envía una alerta de Telegram.

## 4. BrainForge V5 LSTM: sin ventaja demostrada y con features rotos en vivo

- **Solo compra** (nunca emite SELL).
- El "PF 1.64" viene de `ai_lab/04_simulate_trading.py`, que: cuenta una operación por **cada vela** sobre el
  umbral (cientos de trades solapados), no cobra spread ni comisión a ganadoras/perdedoras, y evalúa sobre el
  último 10 % del dataset, que está dentro del 20 % de validación usado para elegir el mejor modelo.
- En vivo pedía 250 velas, pero `dist_macro_H4_pips` usa una SMA de 3200 velas → era **siempre NaN → 0**.
- Las velas de MT5 vienen en hora del servidor (GMT+2/+3) y se trataban como UTC; el modelo se entrenó en UTC →
  los features horarios estaban desplazados 2–3 horas.
- Probado con datos sintéticos: la probabilidad de "ganar" del modelo apenas se mueve (≈ 0.385 ± 0.011) y el
  umbral 0.40 está dentro de ese ruido.
- (Los features `tick_volume` y `spread` valían 0 en todo el entrenamiento —HistData no los trae—; se comprobó
  que el modelo los ignora, así que eso no afecta.)

**Arreglo:** se corrigieron los features (3300 velas, conversión a UTC, inferencia una vez por vela) y la
estrategia queda **desactivada** con `AI_BRAIN_ENABLED = False` hasta que tenga un backtest honesto.

## 5. El backtester también tenía un bug

En todos los simuladores, el ATR se convertía a pips con `/ pip / 10` (dividía por 10 de más), así que SL/TP
siempre salían en el mínimo fijo (p. ej. 15/30). **Arreglo:** `/ pip`. Los resultados de backtests
anteriores no son fiables: hay que volver a correrlos.

## Problemas pendientes (no tocados, requieren decisión)

1. **Credenciales en el repositorio:** `config/settings.py` tiene como valor por defecto el token del bot de
   Telegram y las contraseñas del dashboard. Están en el historial de git → **rota el token con @BotFather** y
   deja solo `os.environ.get(...)` sin valores por defecto.
2. **Hora del VPS en el filtro de noticias:** los eventos se convierten a hora de Bogotá, pero se comparan con
   `datetime.now()` (hora local del VPS). Si el VPS no está en hora de Colombia, las ventanas de noticias y la
   "News Killzone" están desplazadas.
3. **Backtester:** asume que las velas están en UTC (`hour - 5`), pero MT5 entrega hora del servidor
   (GMT+2/+3) → el filtro de sesión del backtest está desplazado respecto al bot en vivo. Además no cobra
   comisión en las pérdidas y calcula la comisión como si fueran 0.1 lotes.
4. **Oráculo Gemini (`ORACLE_ENABLED`)**: aprueba/rechaza entradas con un LLM sin ninguna validación
   estadística y añade latencia. Si falla, aprueba por defecto. Recomendación: desactivarlo hasta medir en
   backtest/demo si mejora algo.
5. **Muy pocas operaciones:** una sola estrategia, un par, M15, con filtro H1, máx. 5 trades/día y 60 min de
   cooldown. Con ~60 días de backtest no hay muestra estadística suficiente para concluir nada.

## Siguiente paso recomendado

1. Correr el backtester corregido (`RUN_BACKTEST.bat`) con **365+ días** y mirar el Profit Factor de
   TTM Squeeze *después de costos*.
2. Solo si PF > 1.2 de forma estable (también fuera de muestra), probar 2–4 semanas en **demo** con esta
   configuración y comparar operación por operación contra el backtest.
3. No volver a activar trailing/IA/oráculo sin haberlos simulado primero.
