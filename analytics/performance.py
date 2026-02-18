"""
📊 Performance Analytics
=========================
Métricas profesionales de rendimiento:
- Win Rate, Profit Factor, Sharpe Ratio
- Max Drawdown, Avg R:R, Expectancy
- Equity Curve, Monthly Breakdown
"""

import csv
import math
from datetime import datetime
from config.settings import BotConfig, ChallengeConfig
from utils.logger import BotLogger


class PerformanceAnalytics:
    """
    Calcula métricas de rendimiento profesionales
    a partir del trade journal.
    """

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.journal_path = BotConfig.JOURNAL_FILE

    def _load_closed_trades(self) -> list[dict]:
        """Carga todos los trades cerrados del journal"""
        trades = []
        try:
            with open(self.journal_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("action") == "CLOSE":
                        trades.append(row)
        except FileNotFoundError:
            self.logger.warning("Journal no encontrado para análisis")
        except Exception as e:
            self.logger.error(f"Error leyendo journal: {e}")
        return trades

    def calculate_metrics(self) -> dict:
        """
        Calcula todas las métricas de rendimiento.

        Returns:
            Dict completo con métricas profesionales
        """
        trades = self._load_closed_trades()

        if not trades:
            return self._empty_metrics()

        # ─── Extraer profits ─────────────────────────────────────────
        profits = []
        for t in trades:
            try:
                profits.append(float(t.get("profit", 0)))
            except (ValueError, TypeError):
                profits.append(0.0)

        if not profits:
            return self._empty_metrics()

        # ─── Métricas básicas ────────────────────────────────────────
        total_trades = len(profits)
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]
        breakeven = [p for p in profits if p == 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0

        # ─── Profits ─────────────────────────────────────────────────
        total_profit = sum(profits)
        gross_profit = sum(wins)
        gross_loss = sum(abs(l) for l in losses)

        # ─── Averages ────────────────────────────────────────────────
        avg_win = (gross_profit / win_count) if win_count > 0 else 0
        avg_loss = (gross_loss / loss_count) if loss_count > 0 else 0
        avg_trade = total_profit / total_trades if total_trades > 0 else 0
        avg_rr = (avg_win / avg_loss) if avg_loss > 0 else float("inf")

        # ─── Profit Factor ───────────────────────────────────────────
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        # ─── Expectancy ──────────────────────────────────────────────
        # E = (Win% × Avg Win) - (Loss% × Avg Loss)
        win_pct = win_rate / 100
        loss_pct = 1 - win_pct
        expectancy = (win_pct * avg_win) - (loss_pct * avg_loss)

        # ─── Largest Win/Loss ────────────────────────────────────────
        largest_win = max(wins) if wins else 0
        largest_loss = min(losses) if losses else 0

        # ─── Consecutive Wins/Losses ─────────────────────────────────
        max_consec_wins = self._max_consecutive(profits, positive=True)
        max_consec_losses = self._max_consecutive(profits, positive=False)

        # ─── Max Drawdown ────────────────────────────────────────────
        max_dd, max_dd_pct = self._calculate_max_drawdown(profits)

        # ─── Sharpe Ratio (simplificado, anualizado) ─────────────────
        sharpe = self._calculate_sharpe_ratio(profits)

        # ─── Recovery Factor ─────────────────────────────────────────
        recovery_factor = (total_profit / max_dd) if max_dd > 0 else float("inf")

        # ─── Equity Curve ────────────────────────────────────────────
        equity_curve = self._build_equity_curve(profits)

        # ─── Return on Account ───────────────────────────────────────
        roi_pct = (total_profit / ChallengeConfig.BALANCE_INICIAL) * 100

        return {
            # Básico
            "total_trades": total_trades,
            "wins": win_count,
            "losses": loss_count,
            "breakeven": len(breakeven),
            "win_rate": round(win_rate, 1),
            # Profits
            "total_profit": round(total_profit, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "roi_pct": round(roi_pct, 2),
            # Averages
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "avg_trade": round(avg_trade, 2),
            "avg_rr": round(avg_rr, 2),
            # Risk metrics
            "profit_factor": round(profit_factor, 2),
            "expectancy": round(expectancy, 2),
            "sharpe_ratio": round(sharpe, 2),
            "recovery_factor": round(recovery_factor, 2),
            # Extremes
            "largest_win": round(largest_win, 2),
            "largest_loss": round(largest_loss, 2),
            "max_consecutive_wins": max_consec_wins,
            "max_consecutive_losses": max_consec_losses,
            # Drawdown
            "max_drawdown": round(max_dd, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            # Curve
            "equity_curve": equity_curve,
        }

    def _max_consecutive(self, profits: list, positive: bool) -> int:
        """Calcula la racha máxima consecutiva de wins o losses"""
        max_streak = 0
        current = 0
        for p in profits:
            if (positive and p > 0) or (not positive and p < 0):
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    def _calculate_max_drawdown(self, profits: list) -> tuple[float, float]:
        """
        Calcula el máximo drawdown de la curva de equity.

        Returns:
            (max_drawdown_dollars, max_drawdown_percent)
        """
        balance = ChallengeConfig.BALANCE_INICIAL
        peak = balance
        max_dd = 0
        max_dd_pct = 0

        for p in profits:
            balance += p
            peak = max(peak, balance)
            dd = peak - balance
            dd_pct = (dd / peak * 100) if peak > 0 else 0

            max_dd = max(max_dd, dd)
            max_dd_pct = max(max_dd_pct, dd_pct)

        return max_dd, max_dd_pct

    def _calculate_sharpe_ratio(self, profits: list, risk_free: float = 0) -> float:
        """
        Calcula el Sharpe Ratio simplificado.
        Anualizado asumiendo ~252 días de trading.
        """
        if len(profits) < 2:
            return 0

        avg_return = sum(profits) / len(profits)
        variance = sum((p - avg_return) ** 2 for p in profits) / (len(profits) - 1)
        std_dev = math.sqrt(variance) if variance > 0 else 0

        if std_dev == 0:
            return 0

        sharpe = (avg_return - risk_free) / std_dev
        # Anualizar (sqrt de ~252 días)
        sharpe_annual = sharpe * math.sqrt(252)

        return sharpe_annual

    def _build_equity_curve(self, profits: list) -> list[float]:
        """Construye la curva de equity"""
        curve = [ChallengeConfig.BALANCE_INICIAL]
        balance = ChallengeConfig.BALANCE_INICIAL
        for p in profits:
            balance += p
            curve.append(round(balance, 2))
        return curve

    def _empty_metrics(self) -> dict:
        """Retorna métricas vacías"""
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "win_rate": 0,
            "total_profit": 0,
            "gross_profit": 0,
            "gross_loss": 0,
            "roi_pct": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "avg_trade": 0,
            "avg_rr": 0,
            "profit_factor": 0,
            "expectancy": 0,
            "sharpe_ratio": 0,
            "recovery_factor": 0,
            "largest_win": 0,
            "largest_loss": 0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            "max_drawdown": 0,
            "max_drawdown_pct": 0,
            "equity_curve": [ChallengeConfig.BALANCE_INICIAL],
        }

    def print_report(self):
        """Imprime un reporte completo de rendimiento"""
        metrics = self.calculate_metrics()

        self.logger.banner("📊 REPORTE DE RENDIMIENTO")
        self.logger.info(f"  Total Trades:        {metrics['total_trades']}")
        self.logger.info(f"  Wins / Losses:       {metrics['wins']} / {metrics['losses']}")
        self.logger.info(f"  Win Rate:            {metrics['win_rate']}%")
        self.logger.separator()
        self.logger.info(f"  Total Profit:        ${metrics['total_profit']:+,.2f}")
        self.logger.info(f"  ROI:                 {metrics['roi_pct']:+.2f}%")
        self.logger.info(f"  Gross Profit:        ${metrics['gross_profit']:,.2f}")
        self.logger.info(f"  Gross Loss:          ${metrics['gross_loss']:,.2f}")
        self.logger.separator()
        self.logger.info(f"  Avg Win:             ${metrics['avg_win']:,.2f}")
        self.logger.info(f"  Avg Loss:            ${metrics['avg_loss']:,.2f}")
        self.logger.info(f"  Avg R:R:             1:{metrics['avg_rr']:.1f}")
        self.logger.separator()
        self.logger.info(f"  Profit Factor:       {metrics['profit_factor']:.2f}")
        self.logger.info(f"  Expectancy:          ${metrics['expectancy']:,.2f}/trade")
        self.logger.info(f"  Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}")
        self.logger.info(f"  Recovery Factor:     {metrics['recovery_factor']:.2f}")
        self.logger.separator()
        self.logger.info(f"  Largest Win:         ${metrics['largest_win']:+,.2f}")
        self.logger.info(f"  Largest Loss:        ${metrics['largest_loss']:+,.2f}")
        self.logger.info(f"  Max Consec. Wins:    {metrics['max_consecutive_wins']}")
        self.logger.info(f"  Max Consec. Losses:  {metrics['max_consecutive_losses']}")
        self.logger.separator()
        self.logger.info(f"  Max Drawdown:        ${metrics['max_drawdown']:,.2f} ({metrics['max_drawdown_pct']:.1f}%)")
        self.logger.separator("═")
