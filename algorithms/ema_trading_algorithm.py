from algorithms.trading_algorithms_class import TradingAlgorithm
import math
import datetime
import json
import time

class EMATradingAlgorithm(TradingAlgorithm):
	def __init__(self, contract_params, ema_period, check_interval, initial_ema, signal_override, tick_size: float = 0.01, sl_ticks: int = 17, tp_ticks_long: int = 28, tp_ticks_short: int = 35, diagnostics_enabled=False, diagnostics_every=5, ib=None, **kwargs):
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
		self.TICK_SIZE = tick_size
		self.SL_TICKS = sl_ticks
		self.TP_TICKS_LONG = tp_ticks_long
		self.TP_TICKS_SHORT = tp_ticks_short
		self.QUANTITY = 1
		# Diagnostics configuration (kept for compatibility, no-op now that base handles EMA diagnostics)
		self.diagnostics_enabled = diagnostics_enabled
		self.diagnostics_every = max(1, int(diagnostics_every)) if diagnostics_enabled else diagnostics_every
		# No extra per-tick diagnostics are emitted by this class anymore; rely on base logging

	def on_tick(self, time_str):
		self.on_tick_common(time_str)
		ctx = self.tick_prologue(
			time_str,
			update_ema=True,
			compute_cci=False,
			price_annotator=lambda: {"EMA": self.live_ema},
		)
		if ctx is None:
			return
		price = ctx["price"]
		if self.has_active_position():
			if self.current_sl_price is not None:
				positions = self.ib.positions()
				self.current_sl_price = self._monitor_stop(positions)
			self._handle_active_position(time_str)
			return
		# Override driven logic
		if self.signal_override == 1 and price < self.live_ema:
			self.log(f"{time_str} ⏩ Buy signal")
			self.signal_override = 0
			self.long_ready = True
			return
		elif self.signal_override == -1 and price > self.live_ema:
			self.log(f"{time_str} ⏩ Sell signal")
			self.signal_override = 0
			self.short_ready = True
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


	def reset_state(self):
		self.signal_override = 0
		self.long_ready = False
		self.short_ready = False
		self.long_counter = 0
		self.short_counter = 0
