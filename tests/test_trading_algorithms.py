import unittest
from unittest.mock import patch
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

    def test_cci14_not_enough_data_and_trim(self):
        algo = CCI14TradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            check_interval=60,
            initial_ema=100,
            ib=self.mock_ib
        )
    # Keep history safely below period so CCI calculation is not performed
    algo.price_history = [100.0] * (algo.CCI_PERIOD - 2)
        # Make get_valid_price return None to simulate missing tick; no price append, no CCI
        with patch.object(algo, 'get_valid_price', return_value=None):
            algo.on_tick('12:00:00')
        # No change to history and no CCI values appended
        self.assertEqual(len(algo.price_history), algo.CCI_PERIOD - 2)
        self.assertEqual(len(algo.cci_values), 0)

    def test_cci14_reset_state(self):
        algo = CCI14TradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            check_interval=60,
            initial_ema=100,
            ib=self.mock_ib
        )
        # Set some state
        algo.ema_fast = 1
        algo.ema_slow = 1
        algo.signal_action = 'BUY'
        algo.signal_time = object()
        algo.price_history = [1]
        algo.cci_values = [1]
        algo.prev_cci = 1
        algo.reset_state()
        self.assertEqual(algo.price_history, [])
        self.assertEqual(algo.cci_values, [])
        self.assertIsNone(algo.prev_cci)
        self.assertIsNone(algo.ema_fast)
        self.assertIsNone(algo.ema_slow)
        self.assertIsNone(algo.signal_action)
        self.assertIsNone(algo.signal_time)

if __name__ == '__main__':
    unittest.main()