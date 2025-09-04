import datetime
import unittest
from unittest.mock import patch

from algorithms.cci14threshold_trading_algorithm import CCI14ThresholdTradingAlgorithm
from algorithms.trading_algorithms_class import Future
from tests.utils import MockIB, MockPosition


class TestCCI14ThresholdTradingAlgorithm(unittest.TestCase):
    def setUp(self):
        self.ib = MockIB()
        self.contract_params = {
            'symbol': 'CL',
            'exchange': 'NYMEX',
            'currency': 'USD',
            'lastTradeDateOrContractMonth': '202601',
        }
        self.algo = CCI14ThresholdTradingAlgorithm(
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
        # Helper to populate enough history
        for p in prices:
            self.algo.price_history.append(p)

    @patch('algorithms.cci14threshold_trading_algorithm.datetime')
    def test_should_trade_now_inside_window(self, mock_dt):
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 9, 0, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta
        # ensure tzinfo handling uses passed tz; ZoneInfo path is not mocked here
        self.assertTrue(self.algo.should_trade_now())

    @patch('algorithms.cci14threshold_trading_algorithm.datetime')
    def test_should_trade_now_outside_window(self, mock_dt):
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 7, 59, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta
        self.assertFalse(self.algo.should_trade_now())

    @patch('algorithms.cci14threshold_trading_algorithm.datetime')
    def test_threshold_sell_triggers_bracket(self, mock_dt):
        # Place time within window
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta

        # craft price history to yield high positive CCI
        base = [100 + i for i in range(20)]  # increasing trend - positive CCI
        self.algo.price_history = base[-14:]
        # Force calculate_and_log_cci to a specific value by monkeypatching stdev/mean path is complex;
        # Instead, directly append a high CCI value and set len>=period to allow flow
        with patch.object(self.algo, 'calculate_and_log_cci', return_value=250.0):
            self.algo.on_tick('12:00:00')
        # Expect one bracket (3 orders) were placed
        self.assertGreaterEqual(len(self.ib.orders()), 3)
        # Last order should be TP or SL with parentId set; we at least see an order was submitted
        self.assertIsNotNone(self.ib.last_order)

    @patch('algorithms.cci14threshold_trading_algorithm.datetime')
    def test_threshold_buy_triggers_bracket(self, mock_dt):
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta

        self.algo.price_history = [100] * 14
        with patch.object(self.algo, 'calculate_and_log_cci', return_value=-250.0):
            self.algo.on_tick('12:00:00')
        self.assertGreaterEqual(len(self.ib.orders()), 3)

    @patch('algorithms.cci14threshold_trading_algorithm.datetime')
    def test_no_trade_when_outside_window(self, mock_dt):
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 7, 0, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta
        self.algo.price_history = [100] * 14
        with patch.object(self.algo, 'calculate_and_log_cci', return_value=250.0):
            self.algo.on_tick('07:00:00')
        self.assertEqual(len(self.ib.orders()), 0)

    @patch('algorithms.cci14threshold_trading_algorithm.datetime')
    def test_block_when_active_position(self, mock_dt):
        mock_dt.datetime.now.return_value = datetime.datetime(2025, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
        mock_dt.datetime.strftime = datetime.datetime.strftime
        mock_dt.time = datetime.time
        mock_dt.timedelta = datetime.timedelta
        # Simulate an active position in same contract
        fut = Future(**self.contract_params)
        # Ensure conId matches algorithm's contract for active position detection
        con_id = getattr(self.algo.contract, 'conId', None) or 123
        self.algo.contract.conId = con_id
        fut.conId = con_id
        self.ib._positions.append(MockPosition(fut, 1))
        self.algo.price_history = [100] * 14
        with patch.object(self.algo, 'calculate_and_log_cci', return_value=250.0):
            self.algo.on_tick('12:00:00')
        self.assertEqual(len(self.ib.orders()), 0)


if __name__ == '__main__':
    unittest.main()
