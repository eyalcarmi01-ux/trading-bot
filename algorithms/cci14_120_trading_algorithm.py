from algorithms.trading_algorithms_class import TradingAlgorithm
from statistics import stdev, mean

# NOTE: File renamed from cci14rev_trading_algorithm.py; class retained as CCI14_120_TradingAlgorithm
class CCI14_120_TradingAlgorithm(TradingAlgorithm):
	def __init__(self, contract_params, check_interval, initial_ema, cli_price: float = None, tick_size: float = 0.01, sl_ticks: int = 20, tp_ticks_long: int = 30, tp_ticks_short: int = 30, **kwargs):
		super().__init__(contract_params, **kwargs)
		# Suppress console output for this algorithm; logs file-only
		self.log_to_console = False
		self.CHECK_INTERVAL = check_interval
		self.EMA_FAST_PERIOD = 10
		self.EMA_SLOW_PERIOD = 200
		self.CCI_PERIOD = 14
		self.K_FAST = 2 / (self.EMA_FAST_PERIOD + 1)
		self.K_SLOW = 2 / (self.EMA_SLOW_PERIOD + 1)
		self.TICK_SIZE = tick_size
		self.SL_TICKS = sl_ticks
		self.TP_TICKS_LONG = tp_ticks_long
		self.TP_TICKS_SHORT = tp_ticks_short
		self.QUANTITY = 1
		self.cci_values = []
		self.prev_cci = None
		self.ema_fast = None
		self.ema_slow = initial_ema
		# Track current trade direction for logging / parity with legacy script
		self.active_direction = None
		self.paused_notice_shown = False
		# Optional colored output for CCI thresholds (legacy style)
		self.enable_color = kwargs.get('enable_color', True)
		self._ANSI_RED = "\033[91m"
		self._ANSI_GREEN = "\033[92m"
		self._ANSI_RESET = "\033[0m"
		# Optional CLI price for startup test order parity with legacy script
		try:
			self.cli_price = float(cli_price) if cli_price is not None else None
		except Exception:
			self.cli_price = None

	def pre_run(self):
		"""Rely on base class generic seeding and indicator priming."""
		# Base run() already executed _auto_seed_generic() before this hook.
		# Nothing to do here unless subclass-specific warmups are required.
		pass

	# CCI calculation moved to base class (calculate_and_log_cci)

	def check_long_condition(self):
		v = self.cci_values
		return len(v) >= 3 and v[-3] < -150 and v[-2] > -150 and v[-1] > v[-2]

	def check_short_condition(self):
		v = self.cci_values
		return len(v) >= 3 and v[-3] >= 150 and v[-2] < 150 and v[-1] < v[-2]

	def on_tick(self, time_str):
		
		# Check for active position
		has_position = self.has_active_position();

		self.on_tick_common(time_str, active_position=has_position)
		ctx = self.tick_prologue(
			time_str,
			update_ema=True,
			compute_cci=True,
			price_annotator=None,
			invalid_price_message="⚠️ Invalid price — skipping (EMAs preserved)",
		)
		if ctx is None:
			return
		price = ctx["price"]
		cci = ctx["cci"]

		# Update CCI history for pattern detection
		self.cci_values.append(cci)
		# Keep only last 10 values for performance
		if len(self.cci_values) > 10:
			self.cci_values.pop(0)
			
		# Update EMA values from base class
		if "ema" in ctx:
			self.ema_slow = ctx["ema"]
		if "ema_fast" in ctx:
			self.ema_fast = ctx["ema_fast"]

		if has_position:
			# If handler closed position (manual SL or fill) clear direction
			if (not has_position) and self.active_direction and self.current_sl_price is None:
				self.active_direction = None
			return
		# Signal detection
		long_signal = self.check_long_condition()
		short_signal = self.check_short_condition()
		ema_filter_long = price >= self.ema_slow
		ema_filter_short = price <= self.ema_slow
		self.log_checking_trade_conditions(time_str)
		if long_signal:
			if ema_filter_long:
				self.log(f"{time_str} ⏳ LONG signal (CCI) + PRICE>EMA200 confirmed — sending bracket order")
				self._set_trade_phase('SIGNAL_PENDING', reason='LONG signal ready')
				prev_entry = self._last_entry_id
				self.place_bracket_order('BUY', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				# Detect if new entry order appeared; track direction
				if self._last_entry_id != prev_entry and self._last_entry_id is not None:
					self.active_direction = 'LONG'
					self.log(f"{time_str} ✅ LONG trade opened (PRICE {round(price,4)} >= EMA200 {round(self.ema_slow,4)})")
			else:
				self.log(f"{time_str} 🔁 LONG CCI pattern but PRICE < EMA200 — filtered out")
		elif short_signal:
			if ema_filter_short:
				self.log(f"{time_str} ⏳ SHORT signal (CCI) + PRICE<EMA200 confirmed — sending bracket order")
				self._set_trade_phase('SIGNAL_PENDING', reason='SHORT signal ready')
				prev_entry = self._last_entry_id
				self.place_bracket_order('SELL', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				if self._last_entry_id != prev_entry and self._last_entry_id is not None:
					self.active_direction = 'SHORT'
					self.log(f"{time_str} ✅ SHORT trade opened (PRICE {round(price,4)} <= EMA200 {round(self.ema_slow,4)})")
			else:
				self.log(f"{time_str} 🔁 SHORT CCI pattern but PRICE > EMA200 — filtered out")
		else:
			self.log(f"{time_str} 🔍 No valid signal — conditions not met\n")

	def reset_state(self):
		self.cci_values = []
		self.prev_cci = None
		self.ema_fast = None
		self.active_direction = None
