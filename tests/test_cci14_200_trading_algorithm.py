import datetime
import unittest
from unittest.mock import patch

from algorithms.cci14_200_trading_algorithm import CCI14_200_TradingAlgorithm
from algorithms.trading_algorithms_class import Future
from tests.utils import MockIB, MockPosition


class TestCCI14_200_TradingAlgorithm(unittest.TestCase):
    def setUp(self):
        self.ib = MockIB()
        self.contract_params = {
            'symbol': 'CL',
            'exchange': 'NYMEX',
            'currency': 'USD',
            'lastTradeDateOrContractMonth': '202601',
        }
        self.algo = CCI14_200_TradingAlgorithm(
            self.contract_params,
            check_interval=1,
            initial_ema=100.0,
            ib=self.ib,
            client_id=111,
            trade_timezone="UTC",
            trade_start=(8, 0),
            trade_end=(20, 0),
        )

    def feed_prices(self, prices):
        for p in prices:
            self.algo.price_history.append(p)

    @patch('algorithms.cci14_200_trading_algorithm.datetime')
    def test_should_trade_now_inside_window(self, mock_dt):
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 9, 0, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta
        self.assertTrue(self.algo.should_trade_now())

    @patch('algorithms.cci14_200_trading_algorithm.datetime')
    def test_should_trade_now_outside_window(self, mock_dt):
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 7, 59, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta
        self.assertFalse(self.algo.should_trade_now())

    @patch('algorithms.cci14_200_trading_algorithm.datetime')
    def test_threshold_sell_triggers_bracket(self, mock_dt):
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta
        base = [100 + i for i in range(20)]
        self.algo.price_history = base[-14:]
        with patch.object(self.algo, 'calculate_and_log_cci', return_value=250.0):
            self.algo.on_tick('12:00:00')
        self.assertGreaterEqual(len(self.ib.orders()), 3)
        self.assertIsNotNone(self.ib.last_order)

    @patch('algorithms.cci14_200_trading_algorithm.datetime')
    def test_threshold_buy_triggers_bracket(self, mock_dt):
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta
        self.algo.price_history = [100] * 14
        with patch.object(self.algo, 'calculate_and_log_cci', return_value=-250.0):
            self.algo.on_tick('12:00:00')
        self.assertGreaterEqual(len(self.ib.orders()), 3)

    @patch('algorithms.cci14_200_trading_algorithm.datetime')
    def test_no_trade_when_outside_window(self, mock_dt):
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 7, 0, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta
        self.algo.price_history = [100] * 14
        with patch.object(self.algo, 'calculate_and_log_cci', return_value=250.0):
            self.algo.on_tick('07:00:00')
        self.assertEqual(len(self.ib.orders()), 0)

    @patch('algorithms.cci14_200_trading_algorithm.datetime')
    def test_block_when_active_position(self, mock_dt):
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta
        fut = Future(**self.contract_params)
        con_id = getattr(self.algo.contract, 'conId', None) or 123
        self.algo.contract.conId = con_id
        fut.conId = con_id
        self.ib._positions.append(MockPosition(fut, 1))
        self.algo.price_history = [100] * 14
        with patch.object(self.algo, 'calculate_and_log_cci', return_value=250.0):
            self.algo.on_tick('12:00:00')
        self.assertEqual(len(self.ib.orders()), 0)

    def test_stdev_cci_calculation_default(self):
        # Default instantiation uses stdev-based CCI (classic_cci=False)
        prices = [100, 101, 99, 102, 98, 100, 101, 99, 100, 100, 101, 102, 99, 100]
        avg = sum(prices[-14:]) / 14
        # Sample standard deviation
        mean = avg
        variance = sum((p - mean) ** 2 for p in prices[-14:]) / (14 - 1)
        stdev_val = variance ** 0.5
        expected = (prices[-1] - avg) / (0.015 * stdev_val) if stdev_val != 0 else 0
        # Silence log noise
        self.algo.log = lambda *a, **k: None
        cci = self.algo.calculate_and_log_cci(prices, '12:00:00')
        self.assertAlmostEqual(cci, expected, places=6)

    def test_classic_cci_calculation_mean_deviation(self):
        # Instantiate with classic_cci=True
        algo_classic = CCI14_200_TradingAlgorithm(
            self.contract_params,
            check_interval=1,
            initial_ema=100.0,
            ib=self.ib,
            client_id=222,
            trade_timezone="UTC",
            trade_start=(8, 0),
            trade_end=(20, 0),
            classic_cci=True,
        )
        prices = [100, 101, 99, 102, 98, 100, 101, 99, 100, 100, 101, 102, 99, 100]
        avg = sum(prices[-14:]) / 14
        mean_dev = sum(abs(p - avg) for p in prices[-14:]) / 14
        expected = (prices[-1] - avg) / (0.015 * mean_dev) if mean_dev != 0 else 0
        algo_classic.log = lambda *a, **k: None
        cci = algo_classic.calculate_and_log_cci(prices, '12:00:00')
        self.assertAlmostEqual(cci, expected, places=6)


if __name__ == '__main__':
    unittest.main()
