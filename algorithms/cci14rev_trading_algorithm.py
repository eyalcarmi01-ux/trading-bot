from algorithms.trading_algorithms_class import TradingAlgorithm
import math
import datetime
from statistics import stdev, mean

class CCI14RevTradingAlgorithm(TradingAlgorithm):
	def __init__(self, contract_params, check_interval, initial_ema, **kwargs):
		super().__init__(contract_params, **kwargs)
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
		self.paused_notice_shown = False

	def calculate_and_log_cci(self, prices, time_str):
		if len(prices) < self.CCI_PERIOD:
			print(f"{time_str} ⚠️ Not enough data for CCI")
			return None
		typical_prices = prices[-self.CCI_PERIOD:]
		avg_tp = mean(typical_prices)
		dev = stdev(typical_prices)
		if dev == 0:
			print(f"{time_str} ⚠️ StdDev is zero — CCI = 0")
			return 0
		cci = (typical_prices[-1] - avg_tp) / (0.015 * dev)
		arrow = "🔼" if self.prev_cci is not None and cci > self.prev_cci else ("🔽" if self.prev_cci is not None and cci < self.prev_cci else "⏸️")
		print(f"{time_str} 📊 CCI14: {round(cci,2)} | Prev: {round(self.prev_cci,2) if self.prev_cci is not None else '—'} {arrow} | Mean: {round(avg_tp,2)} | StdDev: {round(dev,2)}")
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
			print(f"{time_str} ⚠️ Invalid price — skipping\n")
			self.ema_fast = None
			self.ema_slow = None
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
			print(f"{time_str} 🚫 BLOCKED: Trade already active\n")
			return
		# Signal detection
		if self.check_long_condition():
			print(f"{time_str} ⏳ LONG signal detected — sending bracket order")
			self.place_bracket_order('BUY', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
		elif self.check_short_condition():
			print(f"{time_str} ⏳ SHORT signal detected — sending bracket order")
			self.place_bracket_order('SELL', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
		else:
			print(f"{time_str} 🔍 No valid signal — conditions not met\n")

	def reset_state(self):
		self.price_history = []
		self.cci_values = []
		self.prev_cci = None
		self.ema_fast = None
		self.ema_slow = None
