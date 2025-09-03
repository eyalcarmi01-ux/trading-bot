from algorithms.trading_algorithms_class import TradingAlgorithm
import math
import datetime
from statistics import stdev, mean

class CCI14TradingAlgorithm(TradingAlgorithm):
	def __init__(self, contract_params, check_interval, initial_ema, ib=None, **kwargs):
		"""
		client_id (int): Pass as a kwarg to ensure unique IB connection per instance.
		ib: Pass a mock IB instance for testing.
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
		print(f"{time_str} 📊 CCI14: {round(cci,2)} | Prev: {round(self.prev_cci,2) if self.prev_cci else '—'} {arrow} | Mean: {round(avg_tp,2)} | StdDev: {round(dev,2)}")
		self.prev_cci = cci
		return cci

	def on_tick(self, time_str):
		price = self.get_valid_price()
		if price is None:
			print(f"{time_str} ⚠️ Invalid price — skipping\n")
			return
		# Update EMAs
		self.ema_fast = self.calculate_ema(price, self.ema_fast, self.K_FAST)
		self.ema_slow = self.calculate_ema(price, self.ema_slow, self.K_SLOW)
		self.log_price(time_str, price, EMA10=self.ema_fast, EMA200=self.ema_slow)
		# Update price history and CCI
		self.update_price_history(price, maxlen=500)
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
		if len(self.cci_values) >= 2 and self.signal_time is None:
			prev_cci = self.cci_values[-2]
			curr_cci = self.cci_values[-1]
			if prev_cci < 0 < curr_cci and price > self.ema_fast:
				self.signal_time = datetime.datetime.now()
				self.signal_action = 'BUY'
				print(f"{time_str} ⏳ BUY signal detected — waiting 3 minutes")
			elif prev_cci > 0 > curr_cci and price < self.ema_fast:
				self.signal_time = datetime.datetime.now()
				self.signal_action = 'SELL'
				print(f"{time_str} ⏳ SELL signal detected — waiting 3 minutes")
			else:
				print(f"{time_str} 🔍 No valid signal — conditions not met\n")
		# After 3 minutes, send bracket order
		if self.signal_time is not None:
			elapsed = (datetime.datetime.now() - self.signal_time).total_seconds()
			if elapsed >= 180:
				self.place_bracket_order(self.signal_action, self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				print(f"{time_str} ✅ Bracket sent — bot in active position\n")
				self.signal_time = None
				self.signal_action = None
			else:
				remaining = round(180 - elapsed)
				print(f"{time_str} ⏳ Waiting {remaining}s before sending bracket\n")

	def reset_state(self):
		self.price_history = []
		self.cci_values = []
		self.prev_cci = None
		self.ema_fast = None
		self.ema_slow = None
		self.signal_action = None
		self.signal_time = None
