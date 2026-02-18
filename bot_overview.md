# 🤖 Trend Hunter Pro (Tu Bot de $50K)

Este bot ha sido actualizado a una estrategia profesional de **Seguimiento de Tendencia Multi-Temporal**. Ya no es una simple media móvil que pierde dinero en rangos.

## 🧠 Nueva Estrategia: Trend Hunter Pro
El bot ahora "caza" tendencias fuertes y se queda quieto en mercados laterales.

### 1. Filtro "Anti-Lateralidad" (ADX) 🛡️
Antes de operar, el bot consulta el **ADX (Average Directional Index)**.
-   Si ADX < 20: El mercado está "muerto" o lateral. **NO OPERA**.
-   Si ADX > 20: Hay fuerza. **BUSCA ENTRADAS**.

### 2. Filtro de "Marea" (H1) 🌊
El bot opera en M15 (olas), pero consulta el gráfico de **1 Hora (H1)** (la marea).
-   Si el precio en H1 está **arriba** de su EMA 200 → **SOLO COMPRAS** (Prohibido Vender).
-   Si el precio en H1 está **abajo** de su EMA 200 → **SOLO VENTAS** (Prohibido Comprar).
-   *Nunca nadamos contra la corriente.*

### 3. Gatillo de Entrada (M15) 🔫
Solo si las condiciones 1 y 2 se cumplen, buscamos el cruce clásico:
-   **Compra**: EMA 20 cruza arriba de EMA 50.
-   **Venta**: EMA 20 cruza abajo de EMA 50.

---

## 🛡️ Salidas Inteligentes (Dynamic Exits)

### Stop Loss Dinámico (ATR)
Ya no usamos 20 pips fijos. El bot mide la volatilidad del momento (ATR).
-   Mercado tranquilo: Stop corto (ej. 15 pips) → Mayor lotaje.
-   Mercado loco: Stop largo (ej. 40 pips) → Menor lotaje.
-   **Riesgo Monetario**: Siempre fijo en **$250 (0.5%)**, sin importar los pips.

### Trailing Stop Relajado
-   Activación: **+20 pips** de ganancia.
-   Paso: Mueve el stop cada **+10 pips** adicionales.
-   Objetivo: Dejar correr la ganancia y no salir por "ruido" de 5 minutos.

---

## 📋 Resumen Técnico

| Concepto | Valor | Razón |
| :--- | :--- | :--- |
| **Pares** | EURUSD (Principal) | Spread más bajo y líquidez. |
| **Riesgo** | 0.5% ($250) | Conservador para pasar fase 1. |
| **Max DD Diario** | 5% ($2,500) | Hard Limit del Challenge. |
| **Protección** | Cierre al 85% del DD | Salvar la cuenta antes de quemarla. |
| **Noticias** | OFF 30 min antes | Evitar NFP/IPC/FOMC. |

---

## 🚀 Cómo Iniciar

**En tu VPS Windows:**
```powershell
# Fase 1
python main.py --phase 1

# Fase 2
python main.py --phase 2
```

**Monitoreo:** `http://localhost:5050`
