import unittest
from unittest.mock import MagicMock
from algorithms.trading_algorithms_class import TradingAlgorithm
from tests.utils import MockIB


class TestBaseBracketAndPrice(unittest.TestCase):
    def setUp(self):
        self.ib = MockIB()
        params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
        self.algo = TradingAlgorithm(contract_params=params, ib=self.ib)

    def test_place_bracket_buy_sets_parent_and_transmit(self):
        # Force a valid reference price
        self.ib.reqMktData = MagicMock(return_value=MagicMock(last=100.0, close=100.0, ask=100.0, bid=100.0))
        self.algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)
        orders = self.ib.orders()
        # Expect 3 orders: entry (not transmit), SL (not transmit, parentId), TP (transmit, parentId)
        self.assertEqual(len(orders), 3)
        entry, sl, tp = orders[0], orders[1], orders[2]
        self.assertFalse(getattr(entry, 'transmit', True))
        self.assertFalse(getattr(sl, 'transmit', True))
        self.assertTrue(getattr(tp, 'transmit', False))
        self.assertEqual(getattr(sl, 'parentId', None), getattr(entry, 'orderId', None))
        self.assertEqual(getattr(tp, 'parentId', None), getattr(entry, 'orderId', None))
        self.assertIsNotNone(self.algo.current_sl_price)

    def test_place_bracket_sell_sets_parent_and_transmit(self):
        self.ib.reqMktData = MagicMock(return_value=MagicMock(last=100.0, close=100.0, ask=100.0, bid=100.0))
        self.algo.place_bracket_order('SELL', 1, 0.01, 7, 10, 10)
        orders = self.ib.orders()
        self.assertEqual(len(orders), 3)
        entry, sl, tp = orders[0], orders[1], orders[2]
        self.assertFalse(getattr(entry, 'transmit', True))
        self.assertFalse(getattr(sl, 'transmit', True))
        self.assertTrue(getattr(tp, 'transmit', False))
        self.assertEqual(getattr(sl, 'parentId', None), getattr(entry, 'orderId', None))
        self.assertEqual(getattr(tp, 'parentId', None), getattr(entry, 'orderId', None))

    def test_get_valid_price_fallbacks(self):
        # Prioritize last, then close, ask, bid
        # Case: last is None -> uses close
        self.ib.reqMktData = MagicMock(return_value=MagicMock(last=None, close=101.0, ask=100.5, bid=100.25))
        self.assertEqual(self.algo.get_valid_price(), 101.0)
        # Case: last, close None -> uses ask
        self.ib.reqMktData = MagicMock(return_value=MagicMock(last=None, close=None, ask=100.5, bid=100.25))
        self.assertEqual(self.algo.get_valid_price(), 100.5)
        # Case: only bid available
        self.ib.reqMktData = MagicMock(return_value=MagicMock(last=None, close=None, ask=None, bid=99.75))
        self.assertEqual(self.algo.get_valid_price(), 99.75)

    def test_update_price_history_trims(self):
        for i in range(600):
            self.algo.update_price_history(i, maxlen=500)
        self.assertEqual(len(self.algo.price_history), 500)
        self.assertEqual(self.algo.price_history[0], 100)  # first 100 trimmed away


if __name__ == '__main__':
    unittest.main()
