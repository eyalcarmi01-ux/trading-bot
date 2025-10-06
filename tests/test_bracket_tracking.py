Traceback (most recent call last):
  File "/Users/rebeccat/Downloads/trading-bot/main_class.py", line 6, in <module>
    from algorithms.ema_trading_algorithm import EMATradingAlgorithm
  File "/Users/rebeccat/Downloads/trading-bot/algorithms/ema_trading_algorithm.py", line 1, in <module>
    from algorithms.trading_algorithms_class import TradingAlgorithm
  File "/Users/rebeccat/Downloads/trading-bot/algorithms/trading_algorithms_class.py", line 373
    from statistics import mean, stdev
IndentationError: unexpected indentimport unittest
from unittest.mock import MagicMock

from algorithms.trading_algorithms_class import TradingAlgorithm
from tests.utils import MockIB


class TestBracketTracking(unittest.TestCase):
    def setUp(self):
        # Local mock order classes to ensure order objects are created in tests
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
        params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
        self.algo = TradingAlgorithm(contract_params=params, ib=self.ib)
        # Ensure contract is qualified and has all required attributes
        qualified = self.ib.qualifyContracts(self.algo.contract)
        self.algo.contract.symbol = 'CL'
        self.algo.contract.exchange = 'NYMEX'
        self.algo.contract.currency = 'USD'
        self.algo.contract.lastTradeDateOrContractMonth = '202601'
        self.algo.contract.conId = 12345
        # Stable market data
        self.ib.reqMktData = MagicMock(return_value=MagicMock(last=100.0, close=100.0, ask=100.0, bid=100.0))

    def test_tracks_ids_on_place(self):
        # Directly call the order placement logic to ensure IDs are set
        self.algo.place_bracket_order('BUY', 2, 0.01, 7, 10, 10)
        self.assertTrue(all(v is not None for v in (
            self.algo._last_entry_id,
            self.algo._last_sl_id,
            self.algo._last_tp_id,
        )))

    def test_clears_on_monitor_stop_breach(self):
        # Configure SL and market to breach for LONG
        self.algo.current_sl_price = 99.0
        self.algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)
        self.assertIsNotNone(self.algo._last_sl_id)
        # Market now below SL -> breach
        self.ib.reqMktData = MagicMock(return_value=MagicMock(last=98.5, close=98.5, ask=98.5, bid=98.5))
        # Positions: long 1
        from tests.utils import MockPosition
        self.ib.positions = MagicMock(return_value=[MockPosition(self.algo.contract, 1)])
        self.ib.qualifyContracts = MagicMock()
        self.ib.placeOrder = MagicMock()
        self.ib.orders = MagicMock(return_value=[])
        self.algo._monitor_stop(self.ib.positions())
        self.assertIsNone(self.algo._last_sl_id)
        self.assertIsNone(self.algo._last_tp_id)
        self.assertIsNone(self.algo._last_entry_id)
