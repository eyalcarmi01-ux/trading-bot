import datetime
from zoneinfo import ZoneInfo
from statistics import stdev, mean
from typing import Optional, Tuple

from algorithms.cci14_compare_trading_algorithm import CCI14_Compare_TradingAlgorithm


class CCI14_200_TradingAlgorithm(CCI14_Compare_TradingAlgorithm):
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
        trade_timezone: str = "Asia/Jerusalem",
    trade_start: Optional[Tuple[int, int]] = (8, 0),
    trade_end: Optional[Tuple[int, int]] = (23, 0),
        ib=None,
        **kwargs,
    ):
        super().__init__(contract_params, check_interval, initial_ema, ib=ib, **kwargs)
        self.trade_timezone = trade_timezone
        self.trade_start = trade_start
        self.trade_end = trade_end

    def should_trade_now(self, now: Optional[datetime.datetime] = None) -> bool:
        """
        Return True if current time in the configured timezone is within the
        inclusive [trade_start, trade_end] window. If start/end are None, always True.
        """
        if not (self.trade_start and self.trade_end):
            return True
        if now is None:
            now = datetime.datetime.now(ZoneInfo(self.trade_timezone))
        else:
            # Normalize provided naive datetimes to configured TZ, if needed
            if now.tzinfo is None:
                now = now.replace(tzinfo=ZoneInfo(self.trade_timezone))
            else:
                # Convert to target timezone for comparison
                now = now.astimezone(ZoneInfo(self.trade_timezone))
        start_h, start_m = self.trade_start
        end_h, end_m = self.trade_end
        start_t = datetime.time(hour=start_h, minute=start_m)
        end_t = datetime.time(hour=end_h, minute=end_m)
        now_t = now.time()
        return start_t <= now_t <= end_t

    def on_tick(self, time_str: str):
        # Gate by trading window
        if not self.should_trade_now():
            self.log(f"{time_str} ⏸️ Outside trading window — skipping")
            return

        price = self.get_valid_price()
        if price is None:
            self.log(f"{time_str} ⚠️ Invalid price — skipping\n")
            return
        # Explicit legacy-style market price visibility (in addition to structured log_price below)
        try:
            self.log(f"{time_str} 💰 Market Price: {price:.2f}")
            # Minute-aligned market price save line (legacy parity)
            #try:
            #    tz_now = datetime.datetime.now(ZoneInfo(self.trade_timezone))
            #except Exception:
            #    tz_now = datetime.datetime.now()
            #minute_aligned = tz_now.replace(second=0, microsecond=0)
            #self.log(f"{time_str} 📈 Market price saved for {minute_aligned}: {price:.2f}")
        except Exception:
            pass
        # Multi-span EMA update (inherits structures from parent compare algorithm)
        used_multi = False
        try:
            if hasattr(self, '_update_multi_emas'):
                self._update_multi_emas(price)
                used_multi = True
        except Exception:
            used_multi = False
        if not used_multi:
            # Fallback single fast/slow update
            self.ema_fast = self.calculate_ema(price, self.ema_fast, self.K_FAST)
            self.ema_slow = self.calculate_ema(price, self.ema_slow, self.K_SLOW)
        # Standard price + primary EMA log
        self.log_price(time_str, price, EMA10=self.ema_fast, EMA200=self.ema_slow)
        # Additional multi-span diagnostics line (covers legacy "Live EMAs" data richness)
        try:
            if used_multi and hasattr(self, '_maybe_log_multi_ema_diag'):
                self._maybe_log_multi_ema_diag(time_str)
        except Exception:
            pass

        # Update price history and compute CCI14
        prev_len = len(self.price_history) if hasattr(self, 'price_history') else 0
        self.update_price_history(price, maxlen=500)
        try:
            if len(self.price_history) > prev_len:
                # Legacy-style close series / TP addition logs
                self.log(f"{time_str} 📊 Updated close_series with price: {price:.2f} | Length: {len(self.price_history)}")
                self.log(f"{time_str} 📥 New TP added: {price:.2f}")
        except Exception:
            pass
        # Log series maintenance information (legacy parity data points)
        try:
            self.log(f"{time_str} 📊 Updated price_history length: {len(self.price_history)}")
            recent_tp = ", ".join(f"{p:.2f}" for p in self.price_history[-10:])
            self.log(f"{time_str} 🧪 Recent TP Values: {recent_tp}")
            self.log(f"{time_str} 🧼 Cleaned price series length: {len(self.price_history)}")
            # Alias TP Series length (same as price_history here; typical price == close for current implementation)
            # Use actual dynamic length (no fixed cap)
            self.log(f"{time_str} 🧪 TP Series Length After Cleaning: {len(self.price_history)}")
        except Exception:
            pass
        cci = None
        if len(self.price_history) >= self.CCI_PERIOD:
            # Reuse parent's calculation helper
            cci = self.calculate_and_log_cci(self.price_history, time_str)
            if cci is not None:
                self.cci_values.append(cci)
                if len(self.cci_values) > 100:
                    self.cci_values = self.cci_values[-100:]
                # Defensive: ensure concise legacy CCI summary exists (parent already logs, but guard future edits)
                try:
                    # Parent already emits, so this will be skipped unless implementation changes
                    pass
                except Exception:
                    pass

        if cci is None:
            return
        # Always log trade condition evaluation for parity even if active position
        self.log(f"{time_str} 🚦 Checking trade conditions...")
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
            self.log(f"{time_str} 🔍 No trade signal at the moment.")
            if active:
                self.log(f"{time_str} � BLOCKED: Trade already active\n")
