import datetime
from typing import Optional, Tuple

from algorithms.trading_algorithms_class import TradingAlgorithm


class CCI14_200_TradingAlgorithm(TradingAlgorithm):
    """
    A CCI14-based strategy that triggers immediately when CCI crosses ±200:
      - If CCI > +200 -> SELL
      - If CCI < -200 -> BUY

    Adds a should_trade_now window gate using a timezone, start, and end time.
    """

    def __init__(
        self,
        contract_params,
        check_interval,
        initial_ema,
        *,
        tick_size: float = 0.01,
        sl_ticks: int = 20,
        tp_ticks_long: int = 60,
        tp_ticks_short: int = 60,
        trade_timezone: str = "Asia/Jerusalem",
        trade_start: Optional[Tuple[int, int]] = (8, 0),
        trade_end: Optional[Tuple[int, int]] = (23, 0),
        ib=None,
        classic_cci: bool = False,
        **kwargs,
    ):
        # Initialize the common base (connection, logging, contract, seeding config, etc.)
        super().__init__(contract_params, ib=ib, **kwargs)
        # Runtime cadence
        self.CHECK_INTERVAL = check_interval
        # Core indicator config
        self.CCI_PERIOD = 14
        # Trade parameters (kept consistent with legacy behavior)
        self.TICK_SIZE = tick_size
        self.SL_TICKS = sl_ticks
        self.TP_TICKS_LONG = tp_ticks_long
        self.TP_TICKS_SHORT = tp_ticks_short
        self.QUANTITY = 1
        # State containers
        self.price_history = []
        self.cci_values = []
        self.prev_cci = None
        # Trading window configuration
        self.trade_timezone = trade_timezone
        self.trade_start = trade_start
        self.trade_end = trade_end
        # CCI mode toggle (False = stdev-based; True = classic mean deviation)
        self.classic_cci_mode = bool(classic_cci)
        # Ensure starting lifecycle phase explicit for visibility
        try:
            self._set_trade_phase('IDLE', reason='Subclass init')
        except Exception:
            pass

    # should_trade_now is provided by the base class and shared across all algorithms

    def on_tick(self, time_str: str):
        self.on_tick_common(time_str)
        ctx = self.tick_prologue(
            time_str,
            update_ema=True,
            compute_cci=True,
            price_annotator=None,
        )
        if ctx is None:
            return
        price = ctx["price"]
        cci = ctx["cci"]

        if cci is None:
            return
        # Standard condition-eval log
        self.log_checking_trade_conditions(time_str)
        action = None
        if cci > 200:
            action = 'SELL'
        elif cci < -200:
            action = 'BUY'

        active = self.has_active_position()
        if action and not active:
            self.place_bracket_order(
                action,
                self.QUANTITY,
                self.TICK_SIZE,
                self.SL_TICKS,
                self.TP_TICKS_LONG,
                self.TP_TICKS_SHORT,
            )
            self.log(f"{time_str} ✅ Bracket sent ({action}) on CCI14 ±200 threshold\n")
        else:
            self.log(f"{time_str} 🔍 No trade signal at the moment.\n")
            if active:
                self.log(f"{time_str} 🚫 BLOCKED: Trade already active\n")

    def reset_state(self):
        self.price_history = []
        self.cci_values = []
        self.prev_cci = None
