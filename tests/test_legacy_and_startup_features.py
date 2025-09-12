import unittest
from unittest.mock import MagicMock, patch

from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm
from algorithms.cci14_120_trading_algorithm import CCI14_120_TradingAlgorithm
from algorithms.trading_algorithms_class import TradingAlgorithm
from tests.utils import MockIB


class TestFibonacciLegacyMode(unittest.TestCase):
    def setUp(self):
        self.ib = MockIB()
        self.params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')

    def test_pre_run_sets_fib_target_and_ma(self):
        algo = FibonacciTradingAlgorithm(
            contract_params=self.params,
            check_interval=60,
            fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786],
            use_prev_daily_candle=True,
            ib=self.ib,
        )
        # Ensure contract qualified to keep conId accessible
        self.ib.qualifyContracts(algo.contract)
        # Run pre_run to compute targets
        with patch('algorithms.fibonacci_trading_algorithm.datetime') as mock_dt:
            # Make today fixed
            import datetime as _dt
            mock_dt.datetime.now.return_value = _dt.datetime(2025, 1, 2)
            mock_dt.datetime.strftime = _dt.datetime.strftime
            mock_dt.date = _dt.date
            algo.pre_run()
        self.assertIsNotNone(algo.fib_target)
        self.assertIn(algo.fib_type, ('Support', 'Resistance'))
        # MA should be computed from hourly bars
        self.assertIsInstance(algo.ma_120_hourly, (float, type(None)))

    def test_legacy_entry_and_reversal_paths(self):
        # Craft a bullish previous day so target acts as support
        self.ib._historical_overrides[("2 D", "1 day")] = [
            self.ib._Bar(100.0, 110.0, 95.0, 99.0),    # older (bear)
            self.ib._Bar(100.0, 120.0, 90.0, 115.0),   # prev day bullish
        ]
        algo = FibonacciTradingAlgorithm(
            contract_params=self.params,
            check_interval=1,
            fib_levels=[0.618],
            use_prev_daily_candle=True,
            ib=self.ib,
        )
        with patch('algorithms.fibonacci_trading_algorithm.datetime') as mock_dt:
            import datetime as _dt
            mock_dt.datetime.now.return_value = _dt.datetime(2025, 1, 2)
            mock_dt.datetime.strftime = _dt.datetime.strftime
            mock_dt.date = _dt.date
            algo.pre_run()
        # Simulate price at/below target -> enter LONG
        target = algo.fib_target
        algo.get_valid_price = lambda: target - 0.01
        algo.has_active_position = lambda: False
        algo.on_tick('12:00:00')
        self.assertTrue(algo.trade_active)
        self.assertEqual(algo.active_direction, 'LONG')
        # Now force SL breach -> reversal queued for SHORT when price >= target
        algo.get_valid_price = lambda: algo.active_stop_price - 0.01
        algo.on_tick('12:00:01')  # SL hit closes
        self.assertFalse(algo.trade_active)
        self.assertEqual(algo.last_stop_direction, 'LONG')
        # Price rises back above target -> enter SHORT
        algo.get_valid_price = lambda: target + 0.02
        algo.on_tick('12:00:02')
        self.assertTrue(algo.trade_active)
        self.assertEqual(algo.active_direction, 'SHORT')


class TestCCI14RevWarmup(unittest.TestCase):
    def setUp(self):
        self.ib = MockIB()
        self.params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')

    def test_prerun_collects_history_and_bootstraps_ema(self):
    algo = CCI14_120_TradingAlgorithm(contract_params=self.params, check_interval=0, initial_ema=100.0, ib=self.ib)
        # Accelerate sleep
        self.ib.sleep = lambda *_a, **_k: None
        algo.pre_run()
        self.assertGreaterEqual(len(algo.price_history), algo.CCI_PERIOD)
        # EMA fast should be initialized from last 10 samples
        self.assertIsNotNone(algo.ema_fast)


class TestStartupTestOrder(unittest.TestCase):
    def setUp(self):
        self.ib = MockIB()
        self.params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')

    def test_startup_test_order_flow(self):
        algo = TradingAlgorithm(contract_params=self.params, ib=self.ib, test_order_enabled=True, test_order_action='BUY', test_order_qty=1, test_order_fraction=0.5, test_order_delay_sec=0)
        # Speed up sleep and ensure there is a valid price
        self.ib.sleep = lambda *_a, **_k: None
        # Run once
        algo.perform_startup_test_order()
        # One order placed then cancelled (we don’t track cancellations in MockIB; assert last_order exists)
        self.assertIsNotNone(self.ib.last_order)
        # Calling again is a no-op
        last = self.ib.last_order
        algo.perform_startup_test_order()
        self.assertIs(self.ib.last_order, last)


if __name__ == '__main__':
    unittest.main()
