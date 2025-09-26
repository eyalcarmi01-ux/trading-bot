from algorithms.trading_algorithms_class import TradingAlgorithm
import datetime
from collections import deque

class CCI14_Compare_TradingAlgorithm(TradingAlgorithm):
	def __init__(self, contract_params, check_interval, initial_ema, ib=None, *, multi_ema_diagnostics=True, ema_spans=(10,20,32,50,100,200), multi_ema_bootstrap=True, bootstrap_lookback_bars=300, classic_cci=False, **kwargs):
		"""CCI14 compare strategy with optional multi-span EMA diagnostics & bootstrap.

		Parameters:
		- contract_params: dict for IB Future
		- check_interval: seconds between ticks
		- initial_ema: seed value when bootstrap unavailable
		- multi_ema_diagnostics (bool): enable multi-span diagnostics (default True)
		- ema_spans (tuple): spans to track (default legacy set)
		- multi_ema_bootstrap (bool): attempt historical bootstrap if connected
		- bootstrap_lookback_bars (int): approximate bars to request for seeding
		"""
		super().__init__(contract_params, ib=ib, **kwargs)
		self.CHECK_INTERVAL = check_interval
		self.EMA_FAST_PERIOD = 10
		self.EMA_SLOW_PERIOD = 200
		self.CCI_PERIOD = 14
		self.K_FAST = 2 / (self.EMA_FAST_PERIOD + 1)
		self.K_SLOW = 2 / (self.EMA_SLOW_PERIOD + 1)
		self.TICK_SIZE = 0.01
		self.SL_TICKS = 7
		self.TP_TICKS_LONG = 10
		self.TP_TICKS_SHORT = 10
		self.QUANTITY = 1
		self.price_history = []
		self.cci_values = []
		self.prev_cci = None
		self.ema_fast = initial_ema
		self.ema_slow = initial_ema
		self.paused_notice_shown = False
		self.signal_action = None
		self.signal_time = None
		# Multi-EMA diagnostics state
		self.multi_ema_enabled = multi_ema_diagnostics
		self.multi_ema_bootstrap = multi_ema_bootstrap
		self.bootstrap_lookback_bars = int(bootstrap_lookback_bars)
		self.multi_ema_spans = tuple(sorted(set(ema_spans)))
		# Initialize per-span EMAs & short histories for slope (last 10)
		self._multi_emas = {span: initial_ema for span in self.multi_ema_spans}
		self._multi_ema_histories = {span: deque(maxlen=10) for span in self.multi_ema_spans}
		for span in self.multi_ema_spans:
			self._multi_ema_histories[span].append(initial_ema)
		self._multi_ema_k = {span: 2/(span+1) for span in self.multi_ema_spans}
		self._multi_ema_bootstrapped = False
		# CCI mode toggle (False = current stdev-based; True = classic mean deviation)
		self.classic_cci_mode = bool(classic_cci)
		# Ensure starting lifecycle phase in base is explicit
		try:
			self._set_trade_phase('IDLE', reason='Subclass init')
		except Exception:
			pass

	# CCI calculation moved to base class (calculate_and_log_cci)

	def on_tick(self, time_str):
		self.on_tick_common(time_str)
		ctx = self.tick_prologue(
			time_str,
			update_ema=True,
			compute_cci=True,
			price_annotator=lambda: {"EMA10": self.ema_fast, "EMA200": self.ema_slow},
		)
		if ctx is None:
			return
		price = ctx["price"]
		cci = ctx["cci"]
		# Check for active position
		if self.has_active_position():
			self.log(f"{time_str} 🚫 BLOCKED: Trade already active\n")
			return
		# Signal detection
		if len(self.cci_values) >= 2 and self.signal_time is None:
			prev_cci = self.cci_values[-2]
			curr_cci = self.cci_values[-1]
			if prev_cci < 0 < curr_cci and price > self.ema_fast:
				self.signal_time = datetime.datetime.now()
				self.signal_action = 'BUY'
				self._set_trade_phase('SIGNAL_PENDING', reason='BUY CCI cross')
				self.log(f"{time_str} ⏳ BUY signal detected — waiting 3 minutes")
			elif prev_cci > 0 > curr_cci and price < self.ema_fast:
				self.signal_time = datetime.datetime.now()
				self.signal_action = 'SELL'
				self._set_trade_phase('SIGNAL_PENDING', reason='SELL CCI cross')
				self.log(f"{time_str} ⏳ SELL signal detected — waiting 3 minutes")
			else:
				self.log(f"{time_str} 🔍 No valid signal — conditions not met\n")
		# After 3 minutes, send bracket order
		if self.signal_time is not None:
			elapsed = (datetime.datetime.now() - self.signal_time).total_seconds()
			if elapsed >= 180:
				import threading
				def order_thread():
					self.place_bracket_order(self.signal_action, self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
					self.log(f"{time_str} ✅ Bracket sent — bot in active position\n")
				t = threading.Thread(target=order_thread, name="BracketOrderThread")
				t.daemon = True
				t.start()
				self.signal_time = None
				self.signal_action = None
			else:
				remaining = round(180 - elapsed)
				self.log(f"{time_str} ⏳ Waiting {remaining}s before sending bracket\n")

	def pre_run(self):  # Hook invoked by base run()
		"""Rely on base class generic seeding and indicator priming; diagnostics stay enabled."""
		# Base run() already executed _auto_seed_generic() before this hook.
		# Nothing to do here unless subclass-specific warmups are required.
		pass

	def reset_state(self):
		self.price_history = []
		self.cci_values = []
		self.prev_cci = None
		self.ema_fast = None
		self.ema_slow = None
		self.signal_action = None
		self.signal_time = None
