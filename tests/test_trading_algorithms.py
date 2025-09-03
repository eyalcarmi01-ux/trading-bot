import unittest
from unittest.mock import MagicMock
from algorithms.ema_trading_algorithm import EMATradingAlgorithm
from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm
from algorithms.cci14_trading_algorithm import CCI14TradingAlgorithm

class MockIB:
    def __init__(self):
        self._positions = []
        self._orders = []
        self.connected = False
    def connect(self, *a, **kw):
        self.connected = True
    def qualifyContracts(self, contract):
        pass
    def reqMktData(self, contract, snapshot=True):
        class Tick:
            def __init__(self, price):
                self.last = price
                self.close = price
                self.ask = price
                self.bid = price
        return Tick(100.0)  # Simulate a price of 100
    def sleep(self, seconds):
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
        self.connected = False

class TestTradingAlgorithms(unittest.TestCase):
    def setUp(self):
        self.mock_ib = MockIB()
        # Patch TradingAlgorithm base to use mock IB
        EMATradingAlgorithm.__bases__[0].ib = self.mock_ib
        FibonacciTradingAlgorithm.__bases__[0].ib = self.mock_ib
        CCI14TradingAlgorithm.__bases__[0].ib = self.mock_ib

    def test_ema_on_tick(self):
        algo = EMATradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            ema_period=10,
            check_interval=60,
            initial_ema=100,
            signal_override=0,
            ib=self.mock_ib
        )
        algo.on_tick('12:00:00')
        self.assertIsInstance(algo.live_ema, float)

    def test_fibonacci_on_tick(self):
        algo = FibonacciTradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            check_interval=60,
            fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786],
            ib=self.mock_ib
        )
        algo.on_tick('12:00:00')
        self.assertIsInstance(algo.fib_retracements, list)

    def test_cci14_on_tick(self):
        algo = CCI14TradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            check_interval=60,
            initial_ema=100,
            ib=self.mock_ib
        )
        # Pre-fill price history to allow CCI calculation
        algo.price_history = [100.0] * algo.CCI_PERIOD
        algo.on_tick('12:00:00')
        self.assertIsInstance(algo.ema_fast, float)

if __name__ == '__main__':
    unittest.main()