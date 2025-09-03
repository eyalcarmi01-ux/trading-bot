import unittest
from unittest.mock import MagicMock
from algorithms.ema_trading_algorithm import EMATradingAlgorithm
from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm
from algorithms.cci14_trading_algorithm import CCI14TradingAlgorithm
from tests.utils import MockIB

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