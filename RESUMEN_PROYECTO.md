# TX3 PRO BOT - Resumen del Proyecto

## 📌 Descripción General
TX3 PRO BOT es un sistema de trading algorítmico y cuantitativo de alta fidelidad desarrollado en Python. Se integra directamente con la API de MetaTrader 5 (MT5) para ejecutar operaciones automatizadas en el mercado Forex (enfocado en pares mayores como EURUSD y GBPUSD). El sistema combina análisis técnico institucional, gestión estricta de riesgo y modelos de Inteligencia Artificial (Machine Learning y Q-Learning) para la toma de decisiones.

## 🏗️ Arquitectura y Estructura del Proyecto

El proyecto está modularizado en varias carpetas principales:

### 1. `core/` (Núcleo del Sistema)
Contiene la lógica esencial de ejecución y seguridad del bot:
*   **Gestión de Riesgo (`risk_manager.py`)**: Controla el Drawdown, establece límites de pérdida máxima por día, y calcula el tamaño de lote (Position Sizing) basado en el riesgo porcentual.
*   **Gestión de Posiciones (`position_manager.py`)**: Monitorea las operaciones abiertas, ajusta Stop Loss (Trailing Stop) y cierra posiciones cuando es necesario.
*   **Oráculo LLM (`llm_oracle.py`)**: Integración con IA generativa (Gemini) para análisis cualitativo o validación de contexto.
*   **Filtros Contextuales (`news_filter.py`, `session_filter.py`)**: Evita operar en horas de bajo volumen o durante noticias macroeconómicas de alto impacto.

### 2. `strategy/` (Estrategias de Trading)
Implementa diversas estrategias basadas en conceptos institucionales y cuantitativos:
*   **Conceptos Institucionales (SMC)**: `liquidity_sweep.py`, `london_open_purge.py`, `institutional_flow.py`, `ict_silver_bullet.py`.
*   **Modelos Cuantitativos**: `ttm_squeeze.py` (Momentum), `zscore_reversion.py` (Reversión a la media por volatilidad).
*   **Inteligencia Artificial**: `ml_random_forest.py` (Inferencia en vivo usando un modelo pre-entrenado), `q_learning_agent.py` (Agente de aprendizaje por refuerzo).

### 3. `scripts/` (Herramientas y Backtesting)
Scripts independientes para pruebas, optimización y entrenamiento:
*   **Backtester de Alta Fidelidad (`strategy_backtester.py`)**: Simula las estrategias sobre datos históricos de MT5 (actualmente configurado para procesar **1 año de datos** por defecto, evaluando M5, M15 y H1).
*   **Entrenamiento ML (`train_ml_model.py`)**: Módulo para entrenar un Random Forest Classifier usando datos históricos, guardando el "cerebro" en formato `.pkl`.
*   **Q-Learning (`train_q_learning.py`)**: Módulo experimental para entrenar un agente de Reinforcement Learning.
*   **Otras utilidades**: `bot_diagnostics.py`, `simulate_bot.py`, `check_integrity.py`.

### 4. Ejecutables (`.bat`)
Scripts de conveniencia para sistemas Windows/VPS para iniciar el bot (`START_BOT_AND_AI.bat`), hacer backtests (`RUN_BACKTEST.bat`), comprobar instalación, etc.

## 🚀 Estado Actual y Próximos Pasos
*   **Backtester Optimizado**: El backtester se ha configurado recientemente para descargar 1 año de datos (aprox. 106,000 velas entre múltiples temporalidades) para asegurar una muestra estadística robusta de los resultados, consumiendo apenas ~20MB de RAM.
*   **Fusión Cuantitativa + IA (Pendiente)**: Actualmente, el sistema de Machine Learning (`train_ml_model.py`) entrena con datos crudos. El próximo gran paso es **conectar el backtester con el módulo de ML**. La idea es que el backtester genere un CSV con cada señal simulada (indicando si fue WIN o LOSS) y usar ese historial real para que la IA actúe como un "filtro final", prediciendo la probabilidad de éxito de una señal antes de ejecutarla en el mercado real.
*   **Refinamiento de Q-Learning**: El módulo de Q-Learning está presente pero requiere correcciones de estructura para que el loop de entrenamiento actualice la tabla Q correctamente tras simular las operaciones.
