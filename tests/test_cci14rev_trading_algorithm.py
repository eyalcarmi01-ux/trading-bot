from algorithms.cci14rev_trading_algorithm import CCI14RevTradingAlgorithm
from algorithms.ema_trading_algorithm import EMATradingAlgorithm
from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm
from algorithms.cci14_trading_algorithm import CCI14TradingAlgorithm
import unittest
from tests.utils import MockIB

class TestCCI14RevTradingAlgorithm(unittest.TestCase):

    def setUp(self):
    # Provide required constructor args and a simple shared MockIB
    self.ib = MockIB()
        self.algorithm = CCI14RevTradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            check_interval=60,
            initial_ema=100.0,
            ib=self.ib
        )

    def test_initialization(self):
        self.assertIsInstance(self.algorithm, CCI14RevTradingAlgorithm)

    def test_on_tick_runs(self):
        # Should not raise
        self.algorithm.on_tick('12:00:00')

if __name__ == '__main__':
    unittest.main()