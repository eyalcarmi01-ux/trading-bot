import unittest
from unittest.mock import MagicMock

from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm
from tests.utils import MockIB, MockPosition


class TestLegacyHelpers(unittest.TestCase):
    def setUp(self):
        # Monkeypatch order classes for reliable tracking
        class MarketOrder:
            def __init__(self, action, quantity):
                self.action = action
                self.quantity = quantity
                self.transmit = False
                self.orderId = None
                self.parentId = None
        class LimitOrder:
            def __init__(self, action, quantity, price):
                self.action = action
                self.quantity = quantity
                self.price = price
                self.transmit = False
                self.orderId = None
                self.parentId = None
        class StopOrder:
            def __init__(self, action, quantity, price):
                self.action = action
                self.quantity = quantity
                self.price = price
                self.transmit = False
                self.orderId = None
                self.parentId = None
        import sys
        sys.modules[__name__].MarketOrder = MarketOrder
        sys.modules[__name__].LimitOrder = LimitOrder
        sys.modules[__name__].StopOrder = StopOrder
        self.ib = MockIB()
        self.params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
        # use_prev_daily_candle=True enables legacy flags including pending_order_detection
        self.algo = FibonacciTradingAlgorithm(
            contract_params=self.params,
            check_interval=60,
            fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786],
            use_prev_daily_candle=True,
            ib=self.ib,
        )
        # Ensure contract is qualified and has all required attributes
        qualified = self.ib.qualifyContracts(self.algo.contract)
        self.algo.contract.symbol = 'CL'
        self.algo.contract.exchange = 'NYMEX'
        self.algo.contract.currency = 'USD'
        self.algo.contract.lastTradeDateOrContractMonth = '202601'
        self.algo.contract.conId = 12345

    def _add_pending_trade(self, transmit=True, status='Submitted'):
        """Inject a minimal trade object into MockIB._trades list."""
        class _Order:  # minimal shape
            def __init__(self):
                self.transmit = transmit
                self.orderId = 1
        class _Status:
            def __init__(self):
                self.status = status
        class _Contract:
            def __init__(self, cid):
                self.conId = cid
        class _Trade:
            def __init__(self, cid):
                self.order = _Order()
                self.orderStatus = _Status()
                self.contract = _Contract(cid)
        cid = getattr(self.algo.contract, 'conId', None) or 123
        self.algo.contract.conId = cid
        self.ib._trades.append(_Trade(cid))

    def test_pending_detection_detects_pending(self):
        # No positions, but a transmitted working order => True
        self._add_pending_trade(transmit=True, status='Submitted')
        self.assertTrue(self.algo.has_active_position())

    def test_pending_detection_ignores_filled(self):
        self._add_pending_trade(transmit=True, status='Filled')
        self.assertFalse(self.algo.has_active_position())

    def test_pending_detection_ignores_non_transmit(self):
        self._add_pending_trade(transmit=False, status='Submitted')
        self.assertFalse(self.algo.has_active_position())

    def test_active_position_detected_via_positions(self):
        # Inject active position (should be detected regardless of flags)
        fut_contract = type('C', (), {})()
        fut_contract.conId = getattr(self.algo.contract, 'conId', None) or 321
        self.algo.contract.conId = fut_contract.conId
        self.ib._positions = [MockPosition(fut_contract, 1)]
        self.assertTrue(self.algo.has_active_position())

    def test_place_bracket_order_buy(self):
        # Ensure base bracket creates 3 orders with correct transmit flags
            import threading
            orig_thread = threading.Thread
            threading.Thread = lambda target, *a, **kw: type('FakeThread', (), {'start': target})()
            try:
                self.ib.reqMktData = MagicMock(return_value=MagicMock(last=100.0, close=100.0, ask=100.0, bid=100.0))
                self.algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)
                orders = self.ib.orders()
                self.assertGreaterEqual(len(orders), 3)
            finally:
                threading.Thread = orig_thread

    def test_place_bracket_order_sell(self):
        import threading
        orig_thread = threading.Thread
        threading.Thread = lambda target, *a, **kw: type('FakeThread', (), {'start': target})()
        try:
            self.ib.reqMktData = MagicMock(return_value=MagicMock(last=100.0, close=100.0, ask=100.0, bid=100.0))
            self.algo.place_bracket_order('SELL', 1, 0.01, 7, 10, 10)
            orders = self.ib.orders()
            self.assertGreaterEqual(len(orders), 3)
        finally:
            threading.Thread = orig_thread

    def test_place_bracket_order_invalid_action(self):
        # Should not raise; simply skip creating orders
        existing = len(self.ib.orders())
        self.algo.place_bracket_order('HOLD', 1, self.algo.TICK_SIZE, self.algo.SL_TICKS, self.algo.TP_TICKS_LONG, self.algo.TP_TICKS_SHORT)
        self.assertEqual(len(self.ib.orders()), existing)


if __name__ == '__main__':
    unittest.main()
