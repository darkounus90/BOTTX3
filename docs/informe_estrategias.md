# 📈 Informe de Ejecución y Arquitectura de Estrategias - TX3 PRO (Activas)

Este informe detalla la lógica de ejecución y la arquitectura de programación de las **únicas 4 estrategias que se encuentran actualmente activas** en producción. Las demás han sido desactivadas tras las pruebas cuantitativas (al no cumplir con métricas estrictas de Profit Factor o Win Rate).

---

### Distribución de Estrategias Activas por Activo (Watchlist):
- **GBPUSD (The Big Four):** Z-Score Reversion, Institutional Liquidity Sweep (ILS), TTM Squeeze, Institutional Flow SMC.
- **EURUSD (Momentum Puro):** TTM Squeeze.

---

## 1. TTM Squeeze Pro (`ttm_squeeze.py`)
- **Activa en:** EURUSD y GBPUSD
- **Lógica de Ejecución:** Es un "cazador de tendencias" diseñado para operar la inyección de volumen masivo de las sesiones de Londres y Nueva York (3:00 a 12:00 EST). Detecta compresión de volatilidad (mercado sin dirección) y espera la "explosión" o ruptura a favor del momentum institucional.
- **Cómo se programó:** 
  - **Timeframe:** M15 para entrada, H1 para contexto macro.
  - **Indicadores:** Se programaron Bandas de Bollinger (BB) y Canales de Keltner (KC) usando `pandas` midiendo el ATR.
  - **Gatillo:** Se evalúa la variable booleana `squeeze_on` (BB dentro de KC). Dispara cuando en la vela actual se rompe esta condición hacia afuera y se alinea con el cruce de EMAs de momentum (8 y 34) y la EMA 200 de H1.
  - **Riesgo:** Gestión dinámica expansiva basada en ATR (Stop Loss de 1.5 ATR y Take Profit de 4.0 ATR) enfocada en capturar recorridos largos.

## 2. Z-Score Statistical Reversion (`zscore_reversion.py`)
- **Activa en:** GBPUSD
- **Lógica de Ejecución:** Modelo cuantitativo de reversión a la media. Mide estadísticamente a cuántas Desviaciones Estándar (Z-Score) se encuentra el precio respecto a su equilibrio. Cuando la anomalía es muy alta (> 2.5), asume que el precio regresará al promedio.
- **Cómo se programó:**
  - **Filtros Duros:** Tiene un `Kill-Switch` programado para ignorar el par EURUSD (por backtest negativo) y restringe el GBPUSD a una ventana segura de baja volatilidad direccional (13:00 - 17:00 EST).
  - **Cálculo:** Utiliza `df['close'].rolling()` para obtener la SMA_50 y STD_50. La fórmula `(Close - SMA) / STD` genera el Z-Score.
  - **Confirmación:** Requiere que la vela anterior haya superado el umbral Z-Score y la actual haya regresado por debajo, apoyado por una tendencia macro de H1 a favor.

## 3. Institutional Flow SMC 2.0 (`institutional_flow.py`)
- **Activa en:** GBPUSD
- **Lógica de Ejecución:** Top-Down analysis enfocado en Desequilibrios del mercado algorítmico. Mapea gráficamente los FVGs activos en M15. Cuando el precio desciende al FVG de M15 para llenarlo al menos a la mitad (50%), el bot baja de temporalidad a M5 evaluando si ocurrió un cambio de estructura (MSS) a favor del Gap.
- **Cómo se programó:**
  - **Dual Timeframe Syncing:** Obtiene M15 y M5 sincronizados por posición (`copy_rates_from_pos`).
  - **Zona de Mitigación:** Calcula matemáticamente atributos complejos de los desequilibrios: `top`, `bottom` y `mid`.
  - **Gatillo MSS M5:** El precio retrocede dentro de la zona de mitigación y simultáneamente rompe el High previo validado por la media móvil rápida (10 periodos).

## 4. Institutional Liquidity Sweep (`liquidity_sweep.py`)
- **Activa en:** GBPUSD
- **Lógica de Ejecución:** Estrategia basada en trampas y "stop runs". Monitorea los máximos y mínimos absolutos de las últimas 4 horas operativas. Si el mercado pincha uno de esos niveles por un margen ínfimo (< 8 pips) y regresa rápido, lo califica como un "Liquidity Sweep" engañoso.
- **Cómo se programó:**
  - **Regresión Lineal:** Para confirmar que el Sweep revirtió realmente la tendencia, calcula una *Least Squares Moving Average* (LSMA) utilizando polinomios de 1er grado (`numpy.polyfit`).
  - **Criterio de Entrada Multivariable:** Entra si el barrido es < 8 pips y el `close` M5 actual retorna al interior perforando la línea LSMA.
