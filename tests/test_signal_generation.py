import unittest
from unittest.mock import patch
from algorithms.cci14_trading_algorithm import CCI14TradingAlgorithm
from algorithms.ema_trading_algorithm import EMATradingAlgorithm
from algorithms.cci14rev_trading_algorithm import CCI14RevTradingAlgorithm
from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm
from tests.utils import MockIB


class TestCCI14SignalAndDelay(unittest.TestCase):
	def setUp(self):
		self.ib = MockIB()
		self.contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')

	def test_buy_signal_then_delayed_bracket(self):
		algo = CCI14TradingAlgorithm(contract_params=self.contract_params, check_interval=60, initial_ema=50, ib=self.ib)

		# Prepare deterministic EMA and price
		algo.ema_fast = 50.0
		algo.ema_slow = 50.0
		# Pre-fill price history so CCI is computed
		algo.price_history = [50.0] * algo.CCI_PERIOD

		# Patch price and CCI calculator to simulate crossing from - to +
		prices = [60.0, 60.0, 60.0]
		def fake_price():
			return prices.pop(0)

		cci_values = [-10, +10]
		def fake_calc_cci(_, __):
			return cci_values.pop(0) if cci_values else +10

		calls = []
		algo.get_valid_price = fake_price
		algo.calculate_and_log_cci = fake_calc_cci
		algo.place_bracket_order = lambda action, *a, **k: calls.append(action)

		# Control time via patching module datetime used by algo
		import datetime as _dt
		t0 = _dt.datetime(2025, 1, 1, 12, 0, 0)

		class FakeDT:
			@staticmethod
			def now():
				return FakeDT._now

		FakeDT._now = t0
		with patch('algorithms.cci14_trading_algorithm.datetime.datetime', FakeDT):
			# Tick 1: CCI = -10 (no signal)
			algo.on_tick('12:00:00')
			# Ensure cci was appended once
			self.assertTrue(len(algo.cci_values) >= 1)
			# Tick 2: CCI = +10, price > ema_fast -> BUY signal queued
			algo.on_tick('12:00:01')
			self.assertEqual(algo.signal_action, 'BUY')
			self.assertIsNotNone(algo.signal_time)
			# Advance time > 180s and tick again -> bracket should be sent
			FakeDT._now = t0 + _dt.timedelta(seconds=181)
			algo.on_tick('12:03:01')

			self.assertIn('BUY', calls)
			self.assertIsNone(algo.signal_time)
			self.assertIsNone(algo.signal_action)

	def test_sell_signal_then_delayed_bracket(self):
		algo = CCI14TradingAlgorithm(contract_params=self.contract_params, check_interval=60, initial_ema=50, ib=self.ib)

		# Prepare deterministic EMA and price
		algo.ema_fast = 50.0
		algo.ema_slow = 50.0
		algo.price_history = [50.0] * algo.CCI_PERIOD

		# Fake prices constant but below EMA; CCI crosses + to - triggers SELL
		cci_values = [10, -10]
		algo.get_valid_price = lambda: 40.0
		algo.calculate_and_log_cci = lambda *_: cci_values.pop(0) if cci_values else -10

		calls = []
		algo.place_bracket_order = lambda action, *a, **k: calls.append(action)

		import datetime as _dt
		t0 = _dt.datetime(2025, 1, 1, 12, 0, 0)

		class FakeDT:
			@staticmethod
			def now():
				return FakeDT._now

		FakeDT._now = t0
		with patch('algorithms.cci14_trading_algorithm.datetime.datetime', FakeDT):
			algo.on_tick('12:00:00')  # CCI +10
			algo.on_tick('12:00:01')  # CCI -10 -> SELL signal
			self.assertEqual(algo.signal_action, 'SELL')
			FakeDT._now = t0 + _dt.timedelta(seconds=181)
			algo.on_tick('12:03:01')
			self.assertIn('SELL', calls)


class TestEMATriggering(unittest.TestCase):
	def setUp(self):
		self.ib = MockIB()
		self.contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')

	def test_long_ready_triggers_buy_on_cross(self):
		algo = EMATradingAlgorithm(contract_params=self.contract_params, ema_period=10, check_interval=60, initial_ema=100.0, signal_override=0, ib=self.ib)
		algo.live_ema = 100.0
		algo.long_ready = True

		calls = []
		algo.place_bracket_order = lambda action, *_a, **_k: calls.append(action)
		algo.get_valid_price = lambda: 90.0  # price < EMA
		algo.has_active_position = lambda: False

		algo.on_tick('12:00:00')

		self.assertIn('BUY', calls)
		self.assertFalse(algo.long_ready)
		self.assertEqual(algo.long_counter, 0)
		self.assertEqual(algo.signal_override, 0)

	def test_override_buy_flow(self):
		algo = EMATradingAlgorithm(contract_params=self.contract_params, ema_period=10, check_interval=60, initial_ema=100.0, signal_override=1, ib=self.ib)
		algo.live_ema = 100.0

		calls = []
		algo.place_bracket_order = lambda action, *_a, **_k: calls.append(action)
		algo.has_active_position = lambda: False

		# First tick: price above EMA -> counting, no order
		algo.get_valid_price = lambda: 101.0
		algo.on_tick('12:00:00')
		self.assertEqual(algo.signal_override, 1)
		# Second tick: price below EMA -> set long_ready and reset override (no order yet)
		algo.get_valid_price = lambda: 99.0
		algo.on_tick('12:00:01')
		self.assertEqual(algo.signal_override, 0)
		self.assertTrue(algo.long_ready)
		# Third tick: still below EMA -> order placed
		algo.get_valid_price = lambda: 98.5
		algo.on_tick('12:00:02')
		self.assertIn('BUY', calls)

	def test_override_sell_flow(self):
		algo = EMATradingAlgorithm(contract_params=self.contract_params, ema_period=10, check_interval=60, initial_ema=100.0, signal_override=-1, ib=self.ib)
		algo.live_ema = 100.0
		calls = []
		algo.place_bracket_order = lambda action, *_a, **_k: calls.append(action)
		algo.has_active_position = lambda: False
		# First tick: price below EMA -> counting, no order
		algo.get_valid_price = lambda: 99.0
		algo.on_tick('12:00:00')
		self.assertEqual(algo.signal_override, -1)
		# Second: price above EMA -> set short_ready and reset override
		algo.get_valid_price = lambda: 101.0
		algo.on_tick('12:00:01')
		self.assertEqual(algo.signal_override, 0)
		self.assertTrue(algo.short_ready)
		# Third: still above EMA -> order placed
		algo.get_valid_price = lambda: 101.5
		algo.on_tick('12:00:02')
		self.assertIn('SELL', calls)


class TestCCI14RevEMAUpdate(unittest.TestCase):
	def setUp(self):
		self.ib = MockIB()
		self.contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')

	def test_ema_updates_on_tick(self):
		algo = CCI14RevTradingAlgorithm(contract_params=self.contract_params, check_interval=60, initial_ema=100.0, ib=self.ib)
		# Pre-fill to enable fast EMA computation
		algo.price_history = [100.0] * algo.EMA_FAST_PERIOD
		algo.ema_fast = None

		price = 110.0
		algo.get_valid_price = lambda: price
		algo.has_active_position = lambda: False

		algo.on_tick('12:00:00')
		self.assertEqual(algo.ema_fast, price)  # first update equals last price by design here
		self.assertNotEqual(algo.ema_slow, 100.0)  # should have moved toward price


class TestFibonacciSignals(unittest.TestCase):
	def setUp(self):
		self.ib = MockIB()
		self.contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')

	def test_retracement_triggers_order(self):
		algo = FibonacciTradingAlgorithm(contract_params=self.contract_params, check_interval=60, fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786], ib=self.ib)
		# Set prior high/low so we can land near a level
		algo.last_high = 200.0
		algo.last_low = 100.0

		# 61.8% level at 138.2 -> land near here
		price = 138.21
		algo.get_valid_price = lambda: price
		algo.has_active_position = lambda: False

		calls = []
		algo.place_bracket_order = lambda action, *_a, **_k: calls.append(action)
		algo.on_tick('12:00:00')
		self.assertTrue(len(calls) >= 1)

	def test_active_position_blocks_signal(self):
		algo = FibonacciTradingAlgorithm(contract_params=self.contract_params, check_interval=60, fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786], ib=self.ib)
		algo.last_high = 200.0
		algo.last_low = 100.0
		algo.get_valid_price = lambda: 138.21
		algo.has_active_position = lambda: True

		called = []
		algo.place_bracket_order = lambda action, *_a, **_k: called.append(action)
		algo.on_tick('12:00:00')
		self.assertEqual(called, [])

	def test_retracement_reject_triggers_sell(self):
		algo = FibonacciTradingAlgorithm(contract_params=self.contract_params, check_interval=60, fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786], ib=self.ib)
		algo.last_high = 200.0
		algo.last_low = 100.0
		# Price slightly below fib -> signal SELL
		algo.get_valid_price = lambda: 138.19
		calls = []
		algo.place_bracket_order = lambda action, *_a, **_k: calls.append(action)
		algo.on_tick('12:00:00')
		self.assertIn('SELL', calls)

	def test_high_low_and_zero_range_handling(self):
		algo = FibonacciTradingAlgorithm(contract_params=self.contract_params, check_interval=60, fib_levels=[0.5], ib=self.ib)
		# First tick sets both high/low
		algo.get_valid_price = lambda: 150.0
		algo.on_tick('12:00:00')
		self.assertEqual(algo.last_high, 150.0)
		self.assertEqual(algo.last_low, 150.0)
		# Zero range -> no retracements printed/calculated
		self.assertEqual(algo.fib_retracements, [])
