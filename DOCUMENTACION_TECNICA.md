# BOTTX3 Pro - Documentación Técnica para Desarrolladores

## 📌 Visión General del Sistema
**BOTTX3 Pro** es un sistema de trading algorítmico y cuantitativo de alta fidelidad desarrollado en Python, diseñado específicamente para superar desafíos de fondeo (Prop Firms) como el 2 Phase Pro Challenge ($50K). 

El sistema interactúa directamente con **MetaTrader 5 (MT5)** a través de la librería oficial `MetaTrader5` y combina análisis cuantitativo tradicional, Smart Money Concepts (SMC), Machine Learning y Modelos de Lenguaje Grandes (LLMs, específicamente Gemini) para la toma de decisiones, control de riesgo y monitoreo preventivo.

---

## 🏗️ Arquitectura Principal

El proyecto sigue una arquitectura modular orientada a objetos. El punto de entrada principal es `main.py`, que orquesta todos los subsistemas.

### 1. Punto de Entrada (`main.py` y `TX3ProBot`)
La clase `TX3ProBot` es el "cerebro orquestador". Su ciclo de vida es el siguiente:
- **Inicialización (`__init__`)**: Instancia los managers de estado, riesgo, posiciones, portafolio y correlación, además del dashboard local. Carga las estrategias específicas por par (ej. EURUSD, GBPUSD).
- **Restauración de Estado (`_restore_state`)**: Permite que el bot persista su estado en disco entre reinicios, protegiendo variables críticas como el `balance_inicial` y el Drawdown acumulado.
- **Pre-Flight Checks (`run_preflight_checks`)**: Antes de iniciar el loop de trading, verifica la conexión a MT5, permisos del broker (Algo Trading), disponibilidad de símbolos y respuesta de la IA (Oráculo).
- **Main Loop (`run`)**: Un bucle `while self.running` que maneja el "Heartbeat", verifica la conexión continua, gestiona posiciones (cierre en pánico si hay noticias), actualiza el dashboard y lanza hilos secundarios.

---

## ⚙️ Módulos Core (`/core`)

El directorio `core` contiene la lógica de negocio, análisis contextual y protección de capital, que es la máxima prioridad en un bot para Prop Firms.

*   **`RiskManager`**: Gestiona el Drawdown (DD) diario y global. Calcula el tamaño de posición dinámico usando métodos avanzados. Tiene mecanismos para poner al bot en "Modo Defensa" si se acerca a los límites de pérdida.
*   **`PositionManager`**: Se encarga de la apertura y cierre de órdenes en MT5. Escucha los cierres externos (ej. SL/TP tocado por el broker) y actualiza el journal.
*   **`TrailingStopManager`**: Administra el arrastre de Stop Loss para asegurar ganancias una vez que el trade está en positivo.
*   **`PortfolioManager` & `CorrelationManager`**: Manejan la distribución de riesgo multi-par y evitan la sobreexposición en activos altamente correlacionados.
*   **`NewsFilter` & `SessionFilter`**: Módulos críticos que evitan que el bot opere durante zonas muertas o noticias macroeconómicas de alto impacto. 
*   **`PhaseTracker`**: Monitorea el progreso respecto a las fases de la empresa de fondeo (Challenge, Verification, Funded).
*   **`SMCScanner`**: Escáner dedicado de estructuras Smart Money Concepts en múltiples temporalidades.
*   **`LLMOracle` & `AISentiment` (Dr. Quant)**: Componentes que inyectan Inteligencia Artificial. Monitorean la salud del sistema, analizan el sentimiento del mercado y proporcionan diagnósticos de emergencia.

---

## 📈 Estrategias de Trading (`/strategy`)

Las señales de compra/venta se generan en componentes aislados bajo el patrón Strategy (heredando de `base_strategy.py`).

*   **Estrategias Cuantitativas y Técnicas**:
    *   `ZScoreReversionStrategy`: Estrategia de reversión a la media basada en desviaciones estándar de volatilidad.
    *   `TTMSqueezeStrategy`: Modelo de momentum utilizado para capturar expansiones de volatilidad.
    *   `BollingerRSIStrategy`: Combinación clásica de reversión a la media y momentum.
    *   `EMACrossStrategy`: Estrategia de seguimiento de tendencia basada en cruce de medias móviles.
*   **Smart Money Concepts (SMC) & ICT**:
    *   `LiquiditySweepStrategy`: Identifica neutralización de liquidez previa a movimientos direccionales.
    *   `InstitutionalFlowStrategy`: Rastrea el flujo de órdenes institucional.
    *   `LondonOpenPurgeStrategy`: Aprovecha la manipulación de la apertura de Londres.
    *   `ICTSilverBulletStrategy` & `ICTBreakoutStrategy`: Implementaciones de conceptos de Inner Circle Trader centrados en marcos temporales específicos y rupturas.
*   **Agentes Inteligentes**:
    *   `MLRandomForestStrategy`: Inferencia en tiempo real utilizando un modelo de Machine Learning pre-entrenado.
    *   `QLearningAgent`: Agente de Reinforcement Learning experimental.

---

## 🛠️ Herramientas y Mantenimiento (`/scripts` y `.bat`)

El ecosistema de BOTTX3 contiene una suite completa de investigación (Quants) y mantenimiento:

*   **Validación y Backtesting (`/scripts`)**:
    *   `strategy_backtester.py` & `run_auto_backtest.py`: Motor de backtesting de alta fidelidad para simular estrategias sobre datos históricos.
    *   `backtest_adx_compare.py`: Análisis comparativo del filtro ADX en estrategias.
    *   `sensitivity_tester.py`: Prueba la sensibilidad y robustez de los parámetros de las estrategias.
*   **Análisis Post-Trade (`/scripts`)**:
    *   `trade_autopsy.py`: Herramienta para realizar "autopsias" detalladas de operaciones pasadas para entender fallos.
*   **Mantenimiento y ML (`/scripts`)**:
    *   `train_ml_model.py` & `train_q_learning.py`: Entrenadores de modelos de IA.
    *   `genetic_optimizer.py`: Optimizador genético de parámetros.
    *   `check_integrity.py` & `test_oracle_integration.py`: Scripts de diagnóstico y prueba de integraciones.
*   **Ejecutables `.bat`**: 
    *   `START_BOT_AND_AI.bat`: Lanza el sistema en entorno Windows VPS.
    *   `RUN_BACKTEST.bat` & `RUN_AUTOPSY.bat`: Inician motores de validación y análisis post-trade.
    *   `RUN_DIAGNOSTICS.bat` & `DEBUG_VPS_PYTHON.bat`: Herramientas de depuración del entorno.
    *   `COMPARE_SENSITIVITY.bat`: Ejecuta las pruebas de sensibilidad parametral.

---

## 🔄 Flujo de Datos Típico (Ciclo de Vida de un Trade)

1.  El loop en `main.py` iterará llamando al orquestador de estrategias.
2.  `SessionFilter` y `NewsFilter` autorizan la operación verificando condiciones macro y horarias.
3.  La estrategia (ej. `ICTSilverBulletStrategy`) emite una señal direccional.
4.  `PortfolioManager` y `CorrelationManager` validan que la operación no exceda el riesgo global y la correlación permitida.
5.  `RiskManager` valida el DD actual y calcula el lotaje exacto para el SL definido.
6.  `PositionManager` envía la orden a MT5.
7.  Una vez abierta, `TrailingStopManager` y los filtros quedan vigilando la operación hasta su cierre.
8.  Al cerrarse, el TradeJournal se actualiza, el modelo puede realizar una evaluación (Autopsy) y el Dashboard web refleja los nuevos valores.
