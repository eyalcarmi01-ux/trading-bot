from algorithms.trading_algorithms_class import TradingAlgorithm
import math
import datetime

class FibonacciTradingAlgorithm(TradingAlgorithm):
	def __init__(self, contract_params, check_interval, fib_levels, ib=None, **kwargs):
		"""
		client_id (int): Pass as a kwarg to ensure unique IB connection per instance.
		ib: Pass a mock IB instance for testing.
		"""
		super().__init__(contract_params, ib=ib, **kwargs)
		self.CHECK_INTERVAL = check_interval
		self.fib_levels = fib_levels  # List of fib retracement levels, e.g. [0.236, 0.382, 0.5, 0.618, 0.786]
		self.last_high = None
		self.last_low = None
		self.last_signal = None
		self.paused_notice_shown = False
		self.TICK_SIZE = 0.01
		self.SL_TICKS = 17
		self.TP_TICKS_LONG = 28
		self.TP_TICKS_SHORT = 35
		self.QUANTITY = 1
		self.fib_retracements = []
		self.fib_ready = False
		self.fib_direction = None
		self.fib_entry_price = None
		self.fib_stop_price = None
		self.fib_tp_price = None

	def on_tick(self, time_str):
		price = self.get_valid_price()
		if price is None:
			print(f"{time_str} ⚠️ Invalid price — skipping")
			return
		self.log_price(time_str, price)

		# Update high/low for fib calculation
		if self.last_high is None or price > self.last_high:
			self.last_high = price
		if self.last_low is None or price < self.last_low:
			self.last_low = price

		# Calculate Fibonacci retracement levels
		range_ = self.last_high - self.last_low if self.last_high and self.last_low else None
		if range_ and range_ > 0:
			self.fib_retracements = [
				round(self.last_high - range_ * level, 4) for level in self.fib_levels
			]
			print(f"{time_str} 🔢 Fib retracements: {self.fib_retracements}")

		if self.has_active_position():
			if self.current_sl_price is not None:
				positions = self.ib.positions()
				self.current_sl_price = self.monitor_stop(positions)
			self.handle_active_position(time_str)
			return

		# Example logic: Buy if price bounces from a fib level, Sell if price rejects from a fib level
		signal = None
		for fib in self.fib_retracements:
			if abs(price - fib) < self.TICK_SIZE * 2:
				if price > fib:
					signal = 'BUY'
				elif price < fib:
					signal = 'SELL'
				break

		if signal and signal != self.last_signal:
			print(f"{time_str} 🚦 Signal: {signal} at Fib {fib}")
			self.place_bracket_order(signal, self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
			self.last_signal = signal
		else:
			print(f"{time_str} 🔍 No valid signal")

	def reset_state(self):
		self.last_signal = None
		self.last_high = None
		self.last_low = None
		self.fib_retracements = []
		self.fib_ready = False
		self.fib_direction = None
		self.fib_entry_price = None
		self.fib_stop_price = None
		self.fib_tp_price = None
