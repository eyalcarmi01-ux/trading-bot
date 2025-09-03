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

    def test_invalid_price_resets_emas(self):
        # Force invalid price
        self.ib.reqMktData = lambda *_a, **_k: type('Tick', (), {'last': None, 'close': None, 'ask': None, 'bid': None})()
        self.algorithm.on_tick('12:00:00')
        self.assertIsNone(self.algorithm.ema_fast)
        self.assertIsNone(self.algorithm.ema_slow)

    def test_trim_and_reset(self):
        # Allow CCI append and trim
        self.algorithm.price_history = [100.0] * self.algorithm.CCI_PERIOD
        self.ib.reqMktData = lambda *_a, **_k: type('Tick', (), {'last': 100.0, 'close': 100.0, 'ask': 100.0, 'bid': 100.0})()
        for _ in range(130):
            self.algorithm.on_tick('12:00:00')
        self.assertLessEqual(len(self.algorithm.cci_values), 100)
        # Reset clears state
        self.algorithm.reset_state()
        self.assertEqual(self.algorithm.price_history, [])
        self.assertEqual(self.algorithm.cci_values, [])
        self.assertIsNone(self.algorithm.prev_cci)
        self.assertIsNone(self.algorithm.ema_fast)
        self.assertIsNone(self.algorithm.ema_slow)

if __name__ == '__main__':
    unittest.main()