from algorithms.trading_algorithms_class import TradingAlgorithm
import math
import datetime
from statistics import stdev, mean

# NOTE: File renamed from cci14rev_trading_algorithm.py; class retained as CCI14_120_TradingAlgorithm
class CCI14_120_TradingAlgorithm(TradingAlgorithm):
	def __init__(self, contract_params, check_interval, initial_ema, cli_price: float = None, **kwargs):
		super().__init__(contract_params, **kwargs)
		# Suppress console output for this algorithm; logs file-only
		self.log_to_console = False
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
		"""Warm-up: collect 14 prices for CCI and initialize EMA10 from recent history."""
		try:
			self.log("🔍 Preparing CCI14 calculation: collecting price history...\n")
			while len(self.price_history) < self.CCI_PERIOD:
				price = self.get_valid_price()
				# Sleep the check interval to mirror legacy sampling cadence
				self.ib.sleep(self.CHECK_INTERVAL)
				if isinstance(price, (int, float)) and not (isinstance(price, float) and math.isnan(price)):
					self.price_history.append(price)
					self.log(f"⏳ CCI History: {len(self.price_history)}/{self.CCI_PERIOD} collected")
				else:
					self.log("⚠️ Invalid price — skipping")
		except Exception as e:
			self.log(f"⚠️ Warm-up error: {e}")
			return
		# After collecting enough prices, initialize EMA10 from last 10 prices
		if len(self.price_history) >= self.EMA_FAST_PERIOD:
			recent = self.price_history[-self.EMA_FAST_PERIOD:]
			self.ema_fast = recent[0]
			for p in recent[1:]:
				self.ema_fast = self.calculate_ema(p, self.ema_fast, self.K_FAST)
			self.log(f"📊 EMA10 source prices: {recent}")
			self.log(f"📈 Initial EMA10 calculated from history: {self.ema_fast}")
		self.log("✅ CCI14 history complete — bot ready to start\n")

	def calculate_and_log_cci(self, prices, time_str):
		if len(prices) < self.CCI_PERIOD:
			self.log(f"{time_str} ⚠️ Not enough data for CCI")
			return None
		typical_prices = prices[-self.CCI_PERIOD:]
		avg_tp = mean(typical_prices)
		dev = stdev(typical_prices)
		if dev == 0:
			self.log(f"{time_str} ⚠️ StdDev is zero — CCI = 0")
			return 0
		cci = (typical_prices[-1] - avg_tp) / (0.015 * dev)
		arrow = "🔼" if self.prev_cci is not None and cci > self.prev_cci else ("🔽" if self.prev_cci is not None and cci < self.prev_cci else "⏸️")
		cci_display = round(cci, 2)
		if self.enable_color:
			if cci >= 120:
				cci_display = f"{self._ANSI_RED}{round(cci,2)}{self._ANSI_RESET}"
			elif cci <= -120:
				cci_display = f"{self._ANSI_GREEN}{round(cci,2)}{self._ANSI_RESET}"
		dir_fragment = f" | Dir: {self.active_direction}" if self.active_direction else ""
		self.log(f"{time_str} 📊 CCI14: {cci_display} | Prev: {round(self.prev_cci,2) if self.prev_cci is not None else '—'} {arrow} | Mean: {round(avg_tp,2)} | StdDev: {round(dev,2)}{dir_fragment}")
		self.prev_cci = cci
		return cci

	def check_long_condition(self):
		v = self.cci_values
		return len(v) >= 3 and v[-3] < -120 and v[-2] > -120 and v[-1] > v[-2]

	def check_short_condition(self):
		v = self.cci_values
		return len(v) >= 3 and v[-3] >= 120 and v[-2] < 120 and v[-1] < v[-2]

	def on_tick(self, time_str):
		price = self.get_valid_price()
		if price is None:
			self.log(f"{time_str} ⚠️ Invalid price — skipping (EMAs preserved)\n")
			return
		# Update price history
		self.update_price_history(price, maxlen=500)
		# Calculate and log EMA10 using base class utility
		if len(self.price_history) >= self.EMA_FAST_PERIOD:
			last_price = self.price_history[-1]
			# Initialize fast EMA if needed, then update with latest price
			if self.ema_fast is None:
				self.ema_fast = last_price
			self.ema_fast = self.calculate_ema(last_price, self.ema_fast, self.K_FAST)
			self.log_price(time_str, price, EMA10=self.ema_fast)
		# Update EMA200 using base class utility
		if self.ema_slow is not None:
			self.ema_slow = self.calculate_ema(price, self.ema_slow, self.K_SLOW)
		else:
			self.ema_slow = price
		# Calculate CCI
		cci = None
		if len(self.price_history) >= self.CCI_PERIOD:
			cci = self.calculate_and_log_cci(self.price_history, time_str)
			if cci is not None:
				self.cci_values.append(cci)
				if len(self.cci_values) > 100:
					self.cci_values = self.cci_values[-100:]
		# Check for active position
		if self.has_active_position():
			# Invoke base position handler to enable manual SL breach monitoring & fill scanning
			self.handle_active_position(time_str)
			# If handler closed position (manual SL or fill) clear direction
			if (not self.has_active_position()) and self.active_direction and self.current_sl_price is None:
				self.active_direction = None
			return
		# Signal detection
		long_signal = self.check_long_condition()
		short_signal = self.check_short_condition()
		ema_filter_long = self.ema_fast is not None and self.ema_slow is not None and self.ema_fast > self.ema_slow
		ema_filter_short = self.ema_fast is not None and self.ema_slow is not None and self.ema_fast < self.ema_slow
		if long_signal:
			if ema_filter_long:
				self.log(f"{time_str} ⏳ LONG signal (CCI) + EMA10>EMA200 confirmed — sending bracket order")
				self._set_trade_phase('SIGNAL_PENDING', reason='LONG signal ready')
				prev_entry = self._last_entry_id
				self.place_bracket_order('BUY', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				# Detect if new entry order appeared; track direction
				if self._last_entry_id != prev_entry and self._last_entry_id is not None:
					self.active_direction = 'LONG'
					self.log(f"{time_str} ✅ LONG trade opened (EMA10 {round(self.ema_fast,4)} > EMA200 {round(self.ema_slow,4)})")
			else:
				self.log(f"{time_str} 🔁 LONG CCI pattern but EMA10<=EMA200 — filtered out")
		elif short_signal:
			if ema_filter_short:
				self.log(f"{time_str} ⏳ SHORT signal (CCI) + EMA10<EMA200 confirmed — sending bracket order")
				self._set_trade_phase('SIGNAL_PENDING', reason='SHORT signal ready')
				prev_entry = self._last_entry_id
				self.place_bracket_order('SELL', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				if self._last_entry_id != prev_entry and self._last_entry_id is not None:
					self.active_direction = 'SHORT'
					self.log(f"{time_str} ✅ SHORT trade opened (EMA10 {round(self.ema_fast,4)} < EMA200 {round(self.ema_slow,4)})")
			else:
				self.log(f"{time_str} 🔁 SHORT CCI pattern but EMA10>=EMA200 — filtered out")
		else:
			self.log(f"{time_str} 🔍 No valid signal — conditions not met\n")

	def reset_state(self):
		self.price_history = []
		self.cci_values = []
		self.prev_cci = None
		self.ema_fast = None
		self.active_direction = None
