import unittest
from tests.utils import MockIB
from algorithms.cci14_120_trading_algorithm import CCI14_120_TradingAlgorithm


class TestCCI14_120_TradingAlgorithm(unittest.TestCase):
    def setUp(self):
        self.ib = MockIB()
        self.algorithm = CCI14_120_TradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            check_interval=60,
            initial_ema=100.0,
            ib=self.ib
        )

    def test_initialization(self):
        self.assertIsInstance(self.algorithm, CCI14_120_TradingAlgorithm)

    def test_on_tick_runs(self):
        # Bypass connection requirement
        self.algorithm.get_valid_price = lambda: 100.0
        self.algorithm.on_tick('12:00:00')

    def test_invalid_price_preserves_emas(self):
        self.ib.reqMktData = lambda *_a, **_k: type('Tick', (), {'last': None, 'close': None, 'ask': None, 'bid': None})()
        prev_fast = self.algorithm.ema_fast
        prev_slow = self.algorithm.ema_slow
        self.algorithm.on_tick('12:00:00')
        self.assertIs(self.algorithm.ema_fast, prev_fast)
        self.assertEqual(self.algorithm.ema_slow, prev_slow)

    def test_trim_and_reset(self):
        self.algorithm.price_history = [100.0] * self.algorithm.CCI_PERIOD
        self.algorithm.get_valid_price = lambda: 100.0
        for _ in range(130):
            self.algorithm.on_tick('12:00:00')
        self.assertLessEqual(len(self.algorithm.cci_values), 100)
        self.algorithm.reset_state()
        self.assertEqual(self.algorithm.price_history, [])
        self.assertEqual(self.algorithm.cci_values, [])
        self.assertIsNone(self.algorithm.prev_cci)
        self.assertIsNone(self.algorithm.ema_fast)
        self.assertIsNotNone(self.algorithm.ema_slow)

    def test_active_direction_clears_after_position_close(self):
        self.algorithm.active_direction = 'LONG'
        self.algorithm.current_sl_price = None
        self.algorithm.get_valid_price = lambda: 100.0
        calls = []
        def _hap():
            calls.append(1)
            return len(calls) == 1
        self.algorithm.has_active_position = _hap
        self.algorithm.monitor_stop = lambda *_a, **_k: None
        self.algorithm.check_fills_and_reset_state = lambda: None
        self.algorithm.on_tick('12:34:56')
        self.assertIsNone(self.algorithm.active_direction)


if __name__ == '__main__':
    unittest.main()
