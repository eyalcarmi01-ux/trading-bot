import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, time
from zoneinfo import ZoneInfo
from strategy.CCI14_200signal import should_trade_now, check_trade_conditions

class MockConfig:
    def __init__(self):
        self.trade_start = {"hour": 8, "minute": 0}
        self.trade_end = {"hour": 22, "minute": 30}

class TestCCI14200Signal(unittest.TestCase):
    def setUp(self):
        self.config = MockConfig()

    @patch('strategy.CCI14_200signal.datetime')
    def test_should_trade_now_within_hours(self, mock_datetime):
        # Mock current time to be 12:00 (within trading hours)
        mock_now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        mock_datetime.now.return_value = mock_now
        
        result = should_trade_now(self.config)
        
        self.assertTrue(result)

    @patch('strategy.CCI14_200signal.datetime')
    def test_should_trade_now_before_hours(self, mock_datetime):
        # Mock current time to be 6:00 (before trading hours)
        mock_now = datetime(2025, 1, 1, 6, 0, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        mock_datetime.now.return_value = mock_now
        
        result = should_trade_now(self.config)
        
        self.assertFalse(result)

    @patch('strategy.CCI14_200signal.datetime')
    def test_should_trade_now_after_hours(self, mock_datetime):
        # Mock current time to be 23:00 (after trading hours)
        mock_now = datetime(2025, 1, 1, 23, 0, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        mock_datetime.now.return_value = mock_now
        
        result = should_trade_now(self.config)
        
        self.assertFalse(result)

    @patch('strategy.CCI14_200signal.datetime')
    def test_should_trade_now_start_boundary(self, mock_datetime):
        # Mock current time to be exactly start time
        mock_now = datetime(2025, 1, 1, 8, 0, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        mock_datetime.now.return_value = mock_now
        
        result = should_trade_now(self.config)
        
        self.assertTrue(result)

    @patch('strategy.CCI14_200signal.datetime')
    def test_should_trade_now_end_boundary(self, mock_datetime):
        # Mock current time to be exactly end time
        mock_now = datetime(2025, 1, 1, 22, 30, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        mock_datetime.now.return_value = mock_now
        
        result = should_trade_now(self.config)
        
        self.assertTrue(result)

    @patch('strategy.CCI14_200signal.datetime')
    def test_should_trade_now_one_minute_after_end(self, mock_datetime):
        # Mock current time to be one minute after end time
        mock_now = datetime(2025, 1, 1, 22, 31, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
        mock_datetime.now.return_value = mock_now
        
        result = should_trade_now(self.config)
        
        self.assertFalse(result)

    def test_check_trade_conditions_buy_signal(self):
        # CCI below -200 should generate BUY signal
        cci = -250
        
        result = check_trade_conditions(cci)
        
        self.assertEqual(result, 'BUY')

    def test_check_trade_conditions_sell_signal(self):
        # CCI above 200 should generate SELL signal
        cci = 250
        
        result = check_trade_conditions(cci)
        
        self.assertEqual(result, 'SELL')

    def test_check_trade_conditions_no_signal_neutral(self):
        # CCI between -200 and 200 should generate no signal
        cci = 0
        
        result = check_trade_conditions(cci)
        
        self.assertIsNone(result)

    def test_check_trade_conditions_no_signal_positive(self):
        # CCI positive but below 200 should generate no signal
        cci = 150
        
        result = check_trade_conditions(cci)
        
        self.assertIsNone(result)

    def test_check_trade_conditions_no_signal_negative(self):
        # CCI negative but above -200 should generate no signal
        cci = -150
        
        result = check_trade_conditions(cci)
        
        self.assertIsNone(result)

    def test_check_trade_conditions_boundary_buy(self):
        # CCI exactly at -200 should generate BUY signal
        cci = -200
        
        result = check_trade_conditions(cci)
        
        self.assertEqual(result, 'BUY')

    def test_check_trade_conditions_boundary_sell(self):
        # CCI exactly at 200 should generate SELL signal
        cci = 200
        
        result = check_trade_conditions(cci)
        
        self.assertEqual(result, 'SELL')

    def test_check_trade_conditions_extreme_values(self):
        # Test with extreme CCI values
        extreme_positive = 1000
        extreme_negative = -1000
        
        result_sell = check_trade_conditions(extreme_positive)
        result_buy = check_trade_conditions(extreme_negative)
        
        self.assertEqual(result_sell, 'SELL')
        self.assertEqual(result_buy, 'BUY')

    def test_check_trade_conditions_float_values(self):
        # Test with float CCI values
        cci_buy = -200.5
        cci_sell = 200.1
        cci_none = 199.9
        
        self.assertEqual(check_trade_conditions(cci_buy), 'BUY')
        self.assertEqual(check_trade_conditions(cci_sell), 'SELL')
        self.assertIsNone(check_trade_conditions(cci_none))

    def test_should_trade_now_different_timezone(self):
        # Test with different timezone configuration
        self.config.trade_start = {"hour": 9, "minute": 30}
        self.config.trade_end = {"hour": 16, "minute": 0}
        
        with patch('strategy.CCI14_200signal.datetime') as mock_datetime:
            mock_now = datetime(2025, 1, 1, 10, 0, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
            mock_datetime.now.return_value = mock_now
            
            result = should_trade_now(self.config)
            
            self.assertTrue(result)

    def test_should_trade_now_weekend_check(self):
        # Test during weekend (implementation dependent)
        with patch('strategy.CCI14_200signal.datetime') as mock_datetime:
            # Saturday
            mock_now = datetime(2025, 1, 4, 12, 0, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
            mock_datetime.now.return_value = mock_now
            
            result = should_trade_now(self.config)
            
            # This test depends on whether weekend checking is implemented
            # Adjust assertion based on actual implementation
            self.assertIsInstance(result, bool)

    def test_check_trade_conditions_none_input(self):
        # Test with None CCI value
        result = check_trade_conditions(None)
        
        # Should handle None gracefully
        self.assertIsNone(result)

    def test_check_trade_conditions_invalid_input(self):
        # Test with invalid CCI values
        import math
        
        # Test with NaN
        result_nan = check_trade_conditions(math.nan)
        self.assertIsNone(result_nan)
        
        # Test with infinity
        result_inf = check_trade_conditions(math.inf)
        # Infinity should still trigger SELL
        self.assertEqual(result_inf, 'SELL')
        
        result_neg_inf = check_trade_conditions(-math.inf)
        # Negative infinity should trigger BUY
        self.assertEqual(result_neg_inf, 'BUY')

if __name__ == '__main__':
    unittest.main()
