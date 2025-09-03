import unittest
from unittest.mock import MagicMock
from algorithms.trading_algorithms_class import TradingAlgorithm


class _IB:
	def __init__(self):
		self._orders = []
		self._positions = []
	def reqMktData(self, *a, **k):
		return MagicMock(last=100, close=100, ask=100, bid=100)
	def sleep(self, s):
		pass
	def positions(self):
		return self._positions
	def placeOrder(self, contract, order):
		self._orders.append((contract, order))
	def orders(self):
		return self._orders
	def cancelOrder(self, order):
		pass
	def disconnect(self):
		pass
	def connect(self, *a, **k):
		pass
	def qualifyContracts(self, *a, **k):
		pass


class MockPosition:
	def __init__(self, contract, position):
		self.contract = contract
		self.position = position


class TestStateManagement(unittest.TestCase):
	def setUp(self):
		self.ib = _IB()
		params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
		self.algo = TradingAlgorithm(contract_params=params, ib=self.ib)

	def test_connection_handling(self):
		# Ensure reconnect can be called without raising exceptions
		self.ib.disconnect = MagicMock()
		self.ib.connect = MagicMock()
		self.ib.qualifyContracts = MagicMock()
		self.algo.reconnect()
		self.ib.disconnect.assert_called_once()
		self.ib.connect.assert_called_once()
		self.ib.qualifyContracts.assert_called_once()

	def test_place_bracket_order_invalid_action(self):
		# Invalid action should not place orders
		self.ib.reqMktData = MagicMock(return_value=MagicMock(last=100, close=100, ask=100, bid=100))
		self.algo.place_bracket_order('HOLD', 1, 0.01, 7, 10, 10)

	def test_place_bracket_order_invalid_price(self):
		# NaN/None price results in no order placement
		self.ib.reqMktData = MagicMock(return_value=MagicMock(last=None, close=None, ask=None, bid=None))
		self.algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)

	def test_get_valid_price_exception(self):
		self.ib.reqMktData = MagicMock(side_effect=Exception('boom'))
		price = self.algo.get_valid_price()
		self.assertIsNone(price)

	def test_monitor_stop_triggers_close(self):
		# Prepare SL and market price to trigger SL for LONG position
		self.algo.current_sl_price = 99.0
		self.ib.reqMktData = MagicMock(return_value=MagicMock(last=98.5, close=98.5, ask=98.5, bid=98.5))
		pos = MockPosition(self.algo.contract, 1)
		self.ib.positions = MagicMock(return_value=[pos])
		self.ib.qualifyContracts = MagicMock()
		self.ib.placeOrder = MagicMock()
		self.ib.orders = MagicMock(return_value=[])
		new_sl = self.algo.monitor_stop([pos])
		self.assertIsNone(new_sl)
		self.ib.placeOrder.assert_called()

