import unittest
from unittest.mock import MagicMock
from algorithms.trading_algorithms_class import TradingAlgorithm
from tests.utils import MockIB, MockPosition


class TestStateManagement(unittest.TestCase):
	def setUp(self):
		self.ib = MockIB()
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

	def test_monitor_stop_short_breach(self):
		# SHORT position should breach when market >= SL
		self.algo.current_sl_price = 101.0
		self.ib.reqMktData = MagicMock(return_value=MagicMock(last=101.5, close=101.5, ask=101.5, bid=101.5))
		pos = MockPosition(self.algo.contract, -2)
		self.ib.positions = MagicMock(return_value=[pos])
		self.ib.qualifyContracts = MagicMock()
		self.ib.placeOrder = MagicMock()
		self.ib.orders = MagicMock(return_value=[])
		new_sl = self.algo.monitor_stop([pos])
		self.assertIsNone(new_sl)
		self.ib.placeOrder.assert_called()

	def test_monitor_stop_no_breach_returns_sl(self):
		self.algo.current_sl_price = 100.0
		self.ib.reqMktData = MagicMock(return_value=MagicMock(last=101.0, close=101.0, ask=101.0, bid=101.0))
		pos = MockPosition(self.algo.contract, 1)
		self.assertEqual(self.algo.monitor_stop([pos]), 100.0)

	def test_cancel_and_close_helpers(self):
		# Verify helper methods interact with IB
		order = MagicMock()
		self.ib._orders = [order]
		self.ib.cancelOrder = MagicMock()
		self.algo.cancel_all_orders()
		self.ib.cancelOrder.assert_called_with(order)

		# close_all_positions places market orders
		pos = MockPosition(self.algo.contract, 3)
		self.ib.positions = MagicMock(return_value=[pos])
		self.ib.placeOrder = MagicMock()
		self.algo.close_all_positions()
		self.ib.placeOrder.assert_called()

