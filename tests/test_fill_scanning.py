import unittest
from unittest.mock import MagicMock

from algorithms.trading_algorithms_class import TradingAlgorithm
from tests.utils import MockIB


class TestFillScanning(unittest.TestCase):
    def setUp(self):
        self.ib = MockIB()
        params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
        self.algo = TradingAlgorithm(contract_params=params, ib=self.ib)
        # Stable market data for bracket placement
        self.ib.reqMktData = MagicMock(return_value=MagicMock(last=100.0, close=100.0, ask=100.0, bid=100.0))

    def _make_order_status(self, status: str):
        obj = MagicMock()
        obj.status = status
        return obj

    def _make_trade(self, oid: int, status: str):
        order = MagicMock()
        order.orderId = oid
        tr = MagicMock()
        tr.order = order
        tr.orderStatus = self._make_order_status(status)
        return tr

    def test_bracket_order_ids_tracked(self):
        # Place a simple BUY bracket; orderIds should be captured
        self.algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)
        self.assertIsNotNone(self.algo._last_entry_id)
        self.assertIsNotNone(self.algo._last_sl_id)
        self.assertIsNotNone(self.algo._last_tp_id)
        # Sanity: different ids
        self.assertNotEqual(self.algo._last_entry_id, self.algo._last_sl_id)
        self.assertNotEqual(self.algo._last_entry_id, self.algo._last_tp_id)

    def test_fill_scanning_resets_state_on_tp(self):
        # Place bracket and then emulate a filled TP
        self.algo.reset_state = MagicMock()
        self.algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)
        tp_id = self.algo._last_tp_id
        # Inject a trade fill for TP
        self.ib._trades = [self._make_trade(tp_id, 'Filled')]
        self.algo._check_fills_and_reset_state()
        # Ensure tracked ids cleared and reset_state called
        self.assertIsNone(self.algo._last_tp_id)
        self.assertIsNone(self.algo._last_sl_id)
        self.assertIsNone(self.algo._last_entry_id)
        self.algo.reset_state.assert_called()

    def test_fill_scanning_resets_state_on_sl(self):
        # Place bracket and then emulate a filled SL
        self.algo.reset_state = MagicMock()
        self.algo.place_bracket_order('SELL', 1, 0.01, 7, 10, 10)
        sl_id = self.algo._last_sl_id
        # Inject a trade fill for SL
        self.ib._trades = [self._make_trade(sl_id, 'Filled')]
        self.algo._check_fills_and_reset_state()
        # Ensure tracked ids cleared and reset_state called
        self.assertIsNone(self.algo._last_tp_id)
        self.assertIsNone(self.algo._last_sl_id)
        self.assertIsNone(self.algo._last_entry_id)
        self.algo.reset_state.assert_called()
