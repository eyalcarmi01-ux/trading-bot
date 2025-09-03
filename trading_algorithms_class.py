from ib_insync import *
import datetime, time, math
"""
This file has moved to algorithms/trading_algorithms_class.py
"""

class TradingAlgorithm:
	def calculate_ema(self, price, prev_ema, k):
		"""Calculate the next EMA value."""
		return round(price * k + prev_ema * (1 - k), 4) if prev_ema is not None else price

	def log_price(self, time_str, price, **kwargs):
		"""Standardized logging for price and indicators. kwargs can include EMA, CCI, etc."""
		msg = f"{time_str} 📊 Price: {price}"
		for key, value in kwargs.items():
			msg += f" | {key}: {value}"
		print(msg)
	def get_valid_price(self):
		"""Fetch market data and return a valid price or None."""
		try:
			tick = self.ib.reqMktData(self.contract, snapshot=True)
			self.ib.sleep(1)
			price = tick.last or tick.close or tick.ask or tick.bid
			if not isinstance(price, (int, float)) or math.isnan(price):
				return None
			return price
		except Exception as e:
				"""
				This file has moved to algorithms/trading_algorithms_class.py
				"""
	def update_price_history(self, price, maxlen=500):

		if not hasattr(self, 'price_history'):
