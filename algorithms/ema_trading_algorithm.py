from algorithms.trading_algorithms_class import TradingAlgorithm
import math
import datetime
import json
import time

class EMATradingAlgorithm(TradingAlgorithm):
	def __init__(self, contract_params, ema_period, check_interval, initial_ema, signal_override, diagnostics_enabled=False, diagnostics_every=5, ib=None, **kwargs):
		"""EMA strategy with optional extended diagnostics.

		Parameters:
		- contract_params (dict)
		- ema_period (int)
		- check_interval (int seconds)
		- initial_ema (float)
		- signal_override (int: -1 short, 0 none, 1 long)
		- diagnostics_enabled (bool) default False so tests & perf unaffected.
		- diagnostics_every (int) log diagnostics every N ticks when enabled.
		"""
		# Call base initializer first (does not know about diagnostics params)
		super().__init__(contract_params, ib=ib, **kwargs)
		# Ensure EMA algorithm logs to console (designated console-visible strategy)
		self.log_to_console = True
		self.EMA_PERIOD = ema_period
		self.K = 2 / (self.EMA_PERIOD + 1)
		self.CHECK_INTERVAL = check_interval
		self.live_ema = initial_ema
		self.signal_override = signal_override
		self.long_ready = self.short_ready = False
		self.long_counter = self.short_counter = 0
		self.paused_notice_shown = False
		self.TICK_SIZE = 0.01
		self.SL_TICKS = 17
		self.TP_TICKS_LONG = 28
		self.TP_TICKS_SHORT = 35
		self.QUANTITY = 1
		# Diagnostics configuration
		self.diagnostics_enabled = diagnostics_enabled
		self.diagnostics_every = max(1, int(diagnostics_every)) if diagnostics_enabled else diagnostics_every
		self._tick_index = 0
		self.ema_history = []  # store recent EMA values for slope / diagnostics
		# No redundant attributes remain; all state is relevant to EMA logic

	def on_tick(self, time_str):
		# Tick counter (used for diagnostics cadence)
		self._tick_index += 1
		price_latency = None
		if self.diagnostics_enabled:
			_start = time.time()
			price = self.get_valid_price()
			price_latency = time.time() - _start
		else:
			price = self.get_valid_price()
		if price is None:
			self.log(f"{time_str} ⚠️ Invalid price — skipping")
			return
		previous_ema = self.live_ema
		self.live_ema = self.calculate_ema(price, previous_ema, self.K)
		self.ema_history.append(self.live_ema)
		if len(self.ema_history) > 500:
			self.ema_history = self.ema_history[-500:]
		self.log_price(time_str, price, EMA=self.live_ema)
		if self.has_active_position():
			if self.current_sl_price is not None:
				positions = self.ib.positions()
				self.current_sl_price = self._monitor_stop(positions)
			self._handle_active_position(time_str)
			self._maybe_log_diagnostics(time_str, price, price_latency)
			return
		# Override driven logic
		if self.signal_override == 1 and price < self.live_ema:
			self.log(f"{time_str} ⏩ Buy signal")
			self.signal_override = 0
			self.long_ready = True
			self._maybe_log_diagnostics(time_str, price, price_latency)
			return
		elif self.signal_override == -1 and price > self.live_ema:
			self.log(f"{time_str} ⏩ Sell signal")
			self.signal_override = 0
			self.short_ready = True
			self._maybe_log_diagnostics(time_str, price, price_latency)
			return
		if self.signal_override == 1:
			if self.long_counter == 0:
				self.long_counter = 15
				self.log(f"{time_str} ⏩ LONG override initialized | long_counter: {self.long_counter}")
			elif price > self.live_ema:
				self.long_counter += 1
				self.short_counter = 0
				self.log(f"{time_str} ⏳ LONG override counting | long_counter: {self.long_counter}")
				if self.long_counter >= 15 and not self.long_ready:
					self.long_ready = True
					self.log(f"{time_str} ✅ LONG setup ready [override]")
			elif price < self.live_ema:
				self.place_bracket_order('BUY', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				self.long_ready = False
				self.long_counter = 0
				self.signal_override = 0
				self.log(f"{time_str} ✅ LONG override entry executed @ {price}")
			self._maybe_log_diagnostics(time_str, price, price_latency)
			return
		if self.signal_override == -1:
			if self.short_counter == 0:
				self.short_counter = 15
				self.log(f"{time_str} ⏩ SHORT override initialized | short_counter: {self.short_counter}")
			elif price < self.live_ema:
				self.short_counter += 1
				self.long_counter = 0
				self.log(f"{time_str} ⏳ SHORT override counting | short_counter: {self.short_counter}")
				if self.short_counter >= 15 and not self.short_ready:
					self.short_ready = True
					self.log(f"{time_str} ✅ SHORT setup ready [override]")
			elif price > self.live_ema:
				self.place_bracket_order('SELL', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				self.short_ready = False
				self.short_counter = 0
				self.signal_override = 0
				self.log(f"{time_str} ✅ SHORT override entry executed @ {price}")
			self._maybe_log_diagnostics(time_str, price, price_latency)
			return
		# Standard counter logic
		if price > self.live_ema:
			self.long_counter += 1
			self.short_counter = 0
			self.log(f"{time_str} 📈 LONG candle #{self.long_counter}")
			if self.long_counter >= 15 and not self.long_ready:
				self.long_ready = True
				self.log(f"{time_str} ✅ LONG setup ready")
		elif price < self.live_ema:
			self.short_counter += 1
			self.long_counter = 0
			self.log(f"{time_str} 📉 SHORT candle #{self.short_counter}")
			if self.short_counter >= 15 and not self.short_ready:
				self.short_ready = True
				self.log(f"{time_str} ✅ SHORT setup ready")
		else:
			self.log(f"{time_str} ⚖️ NEUTRAL candle — counters reset")
		# Entry conditions
		if self.long_ready and not self.has_active_position() and price < self.live_ema:
			self.place_bracket_order('BUY', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
			self.long_ready = False
			self.long_counter = 0
			self.signal_override = 0
		elif self.short_ready and not self.has_active_position() and price > self.live_ema:
			self.place_bracket_order('SELL', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
			self.short_ready = False
			self.short_counter = 0
			self.signal_override = 0
		else:
			self.log(f"{time_str} 🔍 No valid signal")
		self._maybe_log_diagnostics(time_str, price, price_latency)

	def _ema_slope(self, window=5):
		if len(self.ema_history) <= window:
			return None
		try:
			return round((self.ema_history[-1] - self.ema_history[-window-1]) / window, 5)
		except Exception:
			return None

	def get_diagnostics(self):
		"""Return current diagnostic state as a dict (does not log)."""
		return {
			'tick_index': self._tick_index,
			'ema': self.live_ema,
			'ema_period': self.EMA_PERIOD,
			'ema_slope_per_tick_5': self._ema_slope(5),
			'long_counter': self.long_counter,
			'short_counter': self.short_counter,
			'long_ready': self.long_ready,
			'short_ready': self.short_ready,
			'signal_override': self.signal_override,
			'phase': getattr(self, 'trade_phase', None),
			'has_position': self.has_active_position(),
			'direction': getattr(self, 'current_direction', None),
			'sl_price': self.current_sl_price,
		}

	def _maybe_log_diagnostics(self, time_str, price, price_latency):
		if not self.diagnostics_enabled:
			return
		if self._tick_index % self.diagnostics_every != 0:
			return
		try:
			diag = self.get_diagnostics()
			diag['price'] = price
			if price_latency is not None:
				diag['price_latency_ms'] = round(price_latency * 1000, 2)
			self.log(f"{time_str} 🧪 DIAG {json.dumps(diag, sort_keys=True, default=str)}")
		except Exception:
			pass

	def reset_state(self):
		self.signal_override = 0
		self.long_ready = False
		self.short_ready = False
		self.long_counter = 0
		self.short_counter = 0
