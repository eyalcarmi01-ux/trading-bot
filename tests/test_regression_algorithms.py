from algorithms.ema_trading_algorithm import EMATradingAlgorithm
from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm
from algorithms.cci14_trading_algorithm import CCI14TradingAlgorithm
from algorithms.cci14rev_trading_algorithm import CCI14RevTradingAlgorithm
import unittest
from tests.utils import MockIB

class TestAlgorithmRegression(unittest.TestCase):
    def setUp(self):
        self.mock_ib = MockIB()

    def test_ema_signal_and_state(self):
        algo = EMATradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            ema_period=10,
            check_interval=60,
            initial_ema=100,
            signal_override=1,
            ib=self.mock_ib
        )
        # Simulate a price below EMA to trigger a buy signal
        algo.live_ema = 105
        self.mock_ib.reqMktData = lambda contract, snapshot=True: type('Tick', (), {'last': 100.0, 'close': 100.0, 'ask': 100.0, 'bid': 100.0})()
        algo.on_tick('12:00:00')
        self.assertTrue(algo.long_ready)
        # Simulate a price above EMA to trigger a sell signal
        algo.signal_override = -1
        algo.live_ema = 95
        self.mock_ib.reqMktData = lambda contract, snapshot=True: type('Tick', (), {'last': 100.0, 'close': 100.0, 'ask': 100.0, 'bid': 100.0})()
        algo.on_tick('12:01:00')
        self.assertTrue(algo.short_ready)

    def test_fibonacci_no_signal_on_invalid_price(self):
        algo = FibonacciTradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            check_interval=60,
            fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786],
            ib=self.mock_ib
        )
        # Simulate invalid price
        self.mock_ib.reqMktData = lambda contract, snapshot=True: type('Tick', (), {'last': None, 'close': None, 'ask': None, 'bid': None})()
        algo.on_tick('12:00:00')
        self.assertEqual(algo.last_signal, None)

    def test_cci14_state_and_order(self):
        algo = CCI14TradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            check_interval=60,
            initial_ema=100,
            ib=self.mock_ib
        )
        # Pre-fill price history to allow CCI calculation
        algo.price_history = [100.0] * algo.CCI_PERIOD
        # Simulate a price to update EMA and CCI
        self.mock_ib.reqMktData = lambda contract, snapshot=True: type('Tick', (), {'last': 100.0, 'close': 100.0, 'ask': 100.0, 'bid': 100.0})()
        algo.on_tick('12:00:00')
        self.assertIsInstance(algo.ema_fast, float)
        # Simulate active position blocks new trades
        self.mock_ib._positions = [type('Pos', (), {'contract': algo.contract, 'position': 1})()]
        algo.on_tick('12:01:00')
        # Should not place new order
        self.assertIsNone(self.mock_ib.last_order)

    def test_cci14rev_long_short_conditions(self):
        algo = CCI14RevTradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            check_interval=60,
            initial_ema=100,
            ib=self.mock_ib
        )
        # Pre-fill price history and CCI values for long condition
        algo.price_history = [100.0] * algo.CCI_PERIOD
        algo.cci_values = [-130, -110, -100]
        self.mock_ib.reqMktData = lambda contract, snapshot=True: type('Tick', (), {'last': 100.0, 'close': 100.0, 'ask': 100.0, 'bid': 100.0})()
        algo.on_tick('12:00:00')
        # Pre-fill for short condition
        algo.cci_values = [130, 110, 100]
        algo.on_tick('12:01:00')
        # Should not place order if position is active
        self.mock_ib._positions = [type('Pos', (), {'contract': algo.contract, 'position': 1})()]
        algo.on_tick('12:02:00')
        self.assertIsNone(self.mock_ib.last_order)

    def test_cci14rev_condition_boundaries(self):
        algo = CCI14RevTradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            check_interval=60,
            initial_ema=100,
            ib=self.mock_ib
        )
        # Set price and history to allow CCI eval path
        algo.price_history = [100.0] * algo.CCI_PERIOD
        self.mock_ib.reqMktData = lambda contract, snapshot=True: type('Tick', (), {'last': 100.0, 'close': 100.0, 'ask': 100.0, 'bid': 100.0})()
        # Long boundary: v[-3] == -120 should NOT pass per strict < -120
        algo.cci_values = [-120, -110, -100]
        algo.on_tick('12:00:00')
        # Make it pass: v[-3] < -120
        algo.cci_values = [-121, -110, -100]
        algo.on_tick('12:00:01')
        # Short boundary: v[-3] == 120 should pass per >= 120
        algo.cci_values = [120, 110, 100]
        algo.on_tick('12:00:02')

    def test_ema_neutral_resets_counters(self):
        algo = EMATradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            ema_period=10,
            check_interval=60,
            initial_ema=100,
            signal_override=0,
            ib=self.mock_ib
        )
        algo.live_ema = 100.0
        # prime counters
        algo.long_counter = 2
        algo.short_counter = 3
        # price == EMA -> neutral branch
        self.mock_ib.reqMktData = lambda *_a, **_k: type('Tick', (), {'last': 100.0, 'close': 100.0, 'ask': 100.0, 'bid': 100.0})()
        algo.on_tick('12:00:00')
        self.assertEqual(algo.long_counter, 2)  # neutral branch doesn't alter counters before final no-signal
        self.assertEqual(algo.short_counter, 3)

    def test_fibonacci_duplicate_signal_suppressed(self):
        algo = FibonacciTradingAlgorithm(
            contract_params=dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD'),
            check_interval=60,
            fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786],
            ib=self.mock_ib
        )
        algo.last_high = 200.0
        algo.last_low = 100.0
        algo.get_valid_price = lambda: 138.21
        calls = []
        algo.place_bracket_order = lambda action, *_a, **_k: calls.append(action)
        algo.on_tick('12:00:00')  # first signal
        algo.on_tick('12:00:01')  # same signal should be suppressed by last_signal
        self.assertEqual(calls.count('BUY') + calls.count('SELL'), 1)

if __name__ == '__main__':
    unittest.main()