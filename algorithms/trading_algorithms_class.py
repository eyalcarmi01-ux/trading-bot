from ib_insync import *
import datetime, time, math

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
			print(f"⚠️ Error fetching price: {e}")
			return None

	def update_price_history(self, price, maxlen=500):
		if not hasattr(self, 'price_history'):
			self.price_history = []
		self.price_history.append(price)
		if len(self.price_history) > maxlen:
			self.price_history = self.price_history[-maxlen:]

	def has_active_position(self):
		positions = self.ib.positions()
		return any(getattr(p.contract, 'conId', None) == self.contract.conId and abs(getattr(p, 'position', 0)) > 0 for p in positions)

	def handle_active_position(self, time_str):
		print(f"{time_str} 🔒 Position active — monitoring only")
		if hasattr(self, 'monitor_stop') and callable(self.monitor_stop):
			positions = self.ib.positions()
			self.current_sl_price = self.monitor_stop(positions)
		return
	def __init__(self, contract_params, ib_host='127.0.0.1', ib_port=7497, client_id=17, ib=None):
		# Basic validation of required contract parameters
		if not isinstance(contract_params, dict):
			raise TypeError("contract_params must be a dict")
		required_keys = ['symbol', 'exchange', 'currency']
		for key in required_keys:
			if key not in contract_params or contract_params[key] in (None, ''):
				raise ValueError(f"Missing or empty required contract parameter: {key}")

		if ib is not None:
			self.ib = ib
		else:
			self.ib = IB()
			self.ib.connect(ib_host, ib_port, clientId=client_id)
			self.ib.qualifyContracts(Future(**contract_params))
			print("✅ Connected to IB Gateway")
		self.contract = Future(**contract_params)
		self.current_sl_price = None

	def place_bracket_order(self, action, quantity, tick_size, sl_ticks, tp_ticks_long, tp_ticks_short):
		try:
			contract = self.contract
			tick = self.ib.reqMktData(contract, snapshot=True)
			self.ib.sleep(1)
			ref_price = tick.last or tick.close or tick.ask or tick.bid
			if not isinstance(ref_price, (int, float)) or (isinstance(ref_price, float) and math.isnan(ref_price)):
				print("⚠️ No valid price — skipping order")
				return
			if action.upper() == 'BUY':
				tp_price = round(ref_price + tick_size * tp_ticks_long, 2)
				sl_price = round(ref_price - tick_size * sl_ticks, 2)
				exit_action = 'SELL'
			elif action.upper() == 'SELL':
				tp_price = round(ref_price - tick_size * tp_ticks_short, 2)
				sl_price = round(ref_price + tick_size * sl_ticks, 2)
				exit_action = 'BUY'
			else:
				print("⚠️ Invalid action")
				return
			print(f"📌 Entry ref price: {ref_price}")
			print(f"🎯 TP: {tp_price} | 🛡️ SL: {sl_price}")
			self.current_sl_price = sl_price
			entry_order = MarketOrder(action, quantity)
			entry_order.transmit = False
			self.ib.placeOrder(contract, entry_order)
			sl_order = StopOrder(exit_action, quantity, sl_price)
			sl_order.transmit = False
			sl_order.parentId = entry_order.orderId
			self.ib.placeOrder(contract, sl_order)
			tp_order = LimitOrder(exit_action, quantity, tp_price)
			tp_order.transmit = True
			tp_order.parentId = entry_order.orderId
			self.ib.placeOrder(contract, tp_order)
			print(f"✅ Bracket order sent for {contract.symbol} ({action})")
		except Exception as e:
			print(f"❌ Error in place_bracket_order: {e}")
			return

	def monitor_stop(self, positions):
		contract = self.contract
		if self.current_sl_price is None:
			return None
		tick = self.ib.reqMktData(contract, snapshot=True)
		self.ib.sleep(1)
		market_price = tick.last or tick.close or tick.ask or tick.bid
		for p in positions:
			if p.contract.conId != contract.conId:
				continue
			position_side = 'LONG' if p.position > 0 else 'SHORT'
			sl_hit = (
				position_side == 'LONG' and market_price <= self.current_sl_price or
				position_side == 'SHORT' and market_price >= self.current_sl_price
			)
			if sl_hit:
				print(f"⚠️ Stop breached @ {market_price} vs SL {self.current_sl_price}")
				self.ib.sleep(5)
				action = 'SELL' if p.position > 0 else 'BUY'
				close_contract = p.contract
				if not close_contract.exchange:
					close_contract.exchange = contract.exchange
				self.ib.qualifyContracts(close_contract)
				close_order = MarketOrder(action, abs(p.position))
				self.ib.placeOrder(close_contract, close_order)
				print(f"❌ Manual close: {action} {abs(p.position)}")
				for order in self.ib.orders():
					self.ib.cancelOrder(order)
				print("❌ All open orders cancelled after SL breach")
				self.current_sl_price = None
				return None
		return self.current_sl_price

	def cancel_all_orders(self):
		for order in self.ib.orders():
			self.ib.cancelOrder(order)

	def close_all_positions(self):
		positions = self.ib.positions()
		for p in positions:
			if abs(p.position) > 0:
				action = 'SELL' if p.position > 0 else 'BUY'
				close_order = MarketOrder(action, abs(p.position))
				self.ib.placeOrder(p.contract, close_order)

	def reconnect(self):
		try:
			self.ib.disconnect()
			time.sleep(2)
			self.ib.connect('127.0.0.1', 7497, clientId=17)
			self.ib.qualifyContracts(self.contract)
			print("🔄 Reconnected to IB")
		except Exception as e:
			print(f"❌ Error in reconnect: {e}")
			return

	def wait_for_round_minute(self):
		now = datetime.datetime.now()
		wait_sec = 60 - now.second
		print(f"⏳ Waiting {wait_sec} seconds for round-minute start...")
		time.sleep(wait_sec)
		print(f"🚀 Starting at {datetime.datetime.now().strftime('%H:%M:%S')}\n")

	def run(self):
		self.wait_for_round_minute()
		print(f"🤖 Bot Running | Interval: {getattr(self, 'CHECK_INTERVAL', '?')}s")
		while True:
			try:
				self.ib.sleep(getattr(self, 'CHECK_INTERVAL', 60))
				now = datetime.datetime.now()
				time_str = now.strftime('%H:%M:%S')
				if (now.hour == 22 and now.minute >= 30) or now.hour < 7:
					if now.hour == 22 and now.minute == 50:
						self.cancel_all_orders()
						print(f"{time_str} ❌ All open orders cancelled")
						self.close_all_positions()
						print(f"{time_str} 🛑 Trading shutdown executed at 22:50")
					elif not getattr(self, 'paused_notice_shown', False):
						print(f"{time_str} 😴 Trading paused until 08:00")
						self.paused_notice_shown = True
					continue
				else:
					self.paused_notice_shown = False
				self.on_tick(time_str)
			except Exception as e:
				print(f"{datetime.datetime.now().strftime('%H:%M:%S')} ❌ Error: {e}")
				self.reconnect()
				self.reset_state()

	def on_tick(self, time_str):
		raise NotImplementedError("Subclasses must implement on_tick()")

	def reset_state(self):
		pass
