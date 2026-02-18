# 📊 TX3 Trend Hunter Pro Bot - Informe Completo

## 1. Identidad y Propósito
Este software es un sistema de trading algorítmico autónomo diseñado específicamente para superar el **TX3 Funding Program ($50,000 Challenge)**.
Su arquitectura prioriza la **preservación de capital** (Drawdown Management) sobre la maximización de beneficios, alineándose con las estrictas reglas de las empresas de fondeo.

---

## 2. Estrategia "Trend Hunter Pro" 🦅
El bot opera bajo una filosofía de **seguimiento de tendencia multi-temporal** con filtros de volatilidad. No adivina techos ni suelos; se monta en la ola.

### A. Lógica de Entrada (The 3-Step Filter)
1.  **Filtro de Fuerza (ADX)**:
    -   Consulta el indicador ADX (14 periodos).
    -   **Regla**: Si ADX < 20, el mercado es lateral/ruido. **NO OPERA**.
    -   *Objetivo*: Evitar el 70% de las pérdidas que ocurren en rangos.

2.  **Filtro de Marea (H1 Timeframe)**:
    -   Consulta la EMA 200 en el gráfico de 1 Hora.
    -   **Regla**:
        -   Precio > EMA 200 (H1) → **SOLO COMPRAS**.
        -   Precio < EMA 200 (H1) → **SOLO VENTAS**.
    -   *Objetivo*: Operar siempre a favor de la tendencia mayor. "The trend is your friend".

3.  **Gatillo de Precisión (M15 Timeframe)**:
    -   Espero el cruce de medias rápidas: **EMA 20 vs EMA 50**.
    -   **Regla**:
        -   EMA 20 cruza ARRIBA de EMA 50 + Tendencia Alcista (H1) → **BUY 🟢**.
        -   EMA 20 cruza ABAJO de EMA 50 + Tendencia Bajista (H1) → **SELL 🔴**.

### B. Gestión de Salida (Dynamic Exit)
-   **Stop Loss (SL)**: No es fijo. Se calcula con el **ATR (Average True Range)**.
    -   *Fórmula*: `SL = 1.5 * ATR`.
    -   *Lógica*: En alta volatilidad, el SL se aleja para dar aire. En baja volatilidad, se acerca.
-   **Take Profit (TP)**: Ratio mínimo 1:2.
    -   *Fórmula*: `TP = 3.0 * ATR`.
-   **Trailing Stop 🛡️**:
    -   Se activa cuando la ganancia supera **+20 pips**.
    -   A partir de ahí, el SL persigue al precio cada **+10 pips**.
    -   *Objetivo*: Asegurar ganancias y convertir trades ganadores en "Free Risk".

---

## 3. Gestión de Riesgo (Risk Manager) 🛡️
El "cerebro reptiliano" del bot que impide quemar la cuenta.

| Regla | Límite | Acción del Bot |
| :--- | :--- | :--- |
| **Riesgo por Trade** | **0.5% ($250)** | Calcula lotaje exacto según distancia de SL. Nunca arriesga más. |
| **Pérdida Diaria** | **Max $2,500** | **Warning ($1,750)**: Deja de abrir trades nuevos.<br>**Emergency ($2,125)**: Cierra TODO y se apaga por hoy. |
| **Drawdown Total** | **Max $5,000** | Cierre total y apagado definitivo si se acerca al 85% del límite. |
| **Noticias** | **High Impact** | Pausa 30 min antes y 15 min después de noticias rojas (NFP, CPI, FOMC). |
| **Horario** | **London/NY** | Solo opera en sesiones de alta liquidez (03:00 - 17:00 EST). |

---

## 4. Arquitectura Técnica (Python + MT5)
El bot corre fuera de la terminal, actuando como un "titiritero" que controla MT5.

-   **Nucleo (`main.py`)**: Coordina todos los módulos en un bucle infinito.
-   **Persistencia (`state_manager.py`)**: Guarda el progreso (días operados, profit diario) en un archivo JSON. Si el VPS se reinicia, el bot retoma donde se quedó.
-   **Dashboard Web (`dashboard/`)**: Un servidor Flask que muestra gráficos en tiempo real en `http://localhost:5050`.
-   **Notificaciones (`telegram_notifier.py`)**: Envía alertas al móvil de cada trade y cierre de día.

---

## 5. Instrucciones Operativas

### Requisitos
-   **Sistema Operativo**: Windows 10/11 o Windows Server (VPS).
-   **Plataforma**: MetaTrader 5 (Terminal de escritorio).
-   **Cuenta**: Demo o Real de TX3 Funding.

### Comando de Inicio
Para Fase 1 (Objetivo $5,000):
```bash
python main.py --phase 1
```

Para Fase 2 (Objetivo $2,500):
```bash
python main.py --phase 2
```

---

## 6. Conclusión
Este sistema no es una "máquina de hacer dinero rápido". Es una herramienta profesional de **gestión de probabilidades**.
-   En mercados laterales: Se protege (no opera).
-   En tendencias: Ataca con precisión y deja correr las ganancias.
-   En crisis: Cierra el grifo antes de violar las reglas del challenge.

**Estado Actual**: Listo para Despliegue en VPS v1.0 🚀
