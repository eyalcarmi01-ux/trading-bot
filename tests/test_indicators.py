import unittest
import math
from unittest.mock import patch
from indicators import calculate_cci, calculate_ema, get_latest_emas

class TestIndicators(unittest.TestCase):
    def test_calculate_cci_basic(self):
        # Test basic CCI calculation
        price_series = [100, 101, 102, 103, 104] * 3  # 15 values
        
        cci, avg_tp, dev, arrow = calculate_cci(price_series)
        
        self.assertIsInstance(cci, float)
        self.assertIsInstance(avg_tp, float)
        self.assertIsInstance(dev, float)
        self.assertIn(arrow, ['↑', '↓', '→'])

    def test_calculate_cci_insufficient_data(self):
        # Test with less than 14 data points
        price_series = [100, 101, 102]
        
        cci, avg_tp, dev, arrow = calculate_cci(price_series)
        
        self.assertIsNone(cci)
        self.assertIsNone(avg_tp)
        self.assertIsNone(dev)
        self.assertEqual(arrow, '→')

    def test_calculate_cci_zero_deviation(self):
        # Test with identical prices (zero standard deviation)
        price_series = [100] * 15
        
        cci, avg_tp, dev, arrow = calculate_cci(price_series)
        
        self.assertEqual(cci, 0)
        self.assertEqual(avg_tp, 100)
        self.assertEqual(dev, 0)

    def test_calculate_cci_with_invalid_values(self):
        # Test with NaN and None values
        price_series = [100, 101, math.nan, None, 104] * 3
        
        cci, avg_tp, dev, arrow = calculate_cci(price_series)
        
        # Should handle invalid values gracefully
        self.assertIsInstance(cci, (float, type(None)))

    def test_calculate_ema_basic(self):
        prices = [100, 101, 102, 103, 104]
        period = 3
        
        ema = calculate_ema(prices, period)
        
        self.assertIsInstance(ema, float)
        self.assertGreater(ema, 100)
        self.assertLess(ema, 104)

    def test_calculate_ema_insufficient_data(self):
        prices = [100, 101]
        period = 5
        
        ema = calculate_ema(prices, period)
        
        # Should return the last price or handle gracefully
        self.assertIsInstance(ema, (float, type(None)))

    def test_calculate_ema_empty_data(self):
        prices = []
        period = 5
        
        ema = calculate_ema(prices, period)
        
        self.assertIsNone(ema)

    def test_calculate_ema_single_value(self):
        prices = [100]
        period = 5
        
        ema = calculate_ema(prices, period)
        
        self.assertEqual(ema, 100)

    def test_get_latest_emas_basic(self):
        close_series = list(range(100, 150))  # 50 values
        spans = (10, 20, 50)
        
        emas = get_latest_emas(close_series, spans)
        
        self.assertEqual(len(emas), 3)
        self.assertTrue(all(isinstance(ema, float) for ema in emas))

    def test_get_latest_emas_insufficient_data(self):
        close_series = [100, 101, 102]
        spans = (10, 20, 50)
        
        emas = get_latest_emas(close_series, spans)
        
        # Should handle insufficient data gracefully
        self.assertEqual(len(emas), 3)

    def test_get_latest_emas_empty_data(self):
        close_series = []
        spans = (10, 20, 50)
        
        emas = get_latest_emas(close_series, spans)
        
        self.assertEqual(len(emas), 3)
        self.assertTrue(all(ema is None for ema in emas))

    def test_calculate_cci_trending_up(self):
        # Test upward trending prices
        price_series = list(range(100, 115))  # 15 increasing values
        
        cci, avg_tp, dev, arrow = calculate_cci(price_series)
        
        self.assertGreater(cci, 0)  # Should be positive for uptrend
        self.assertEqual(arrow, '↑')

    def test_calculate_cci_trending_down(self):
        # Test downward trending prices
        price_series = list(range(115, 100, -1))  # 15 decreasing values
        
        cci, avg_tp, dev, arrow = calculate_cci(price_series)
        
        self.assertLess(cci, 0)  # Should be negative for downtrend
        self.assertEqual(arrow, '↓')

    def test_calculate_cci_extreme_values(self):
        # Test with extreme price movements
        price_series = [100] * 7 + [200] * 7 + [100]  # 15 values with large jump
        
        cci, avg_tp, dev, arrow = calculate_cci(price_series)
        
        self.assertIsInstance(cci, float)
        self.assertIsInstance(dev, float)
        self.assertGreater(abs(cci), 100)  # Should show extreme reading

    def test_ema_with_nan_values(self):
        prices = [100, 101, math.nan, 103, 104]
        period = 3
        
        ema = calculate_ema(prices, period)
        
        # Should handle NaN values gracefully
        self.assertIsInstance(ema, (float, type(None)))

    def test_ema_all_nan_values(self):
        prices = [math.nan] * 10
        period = 5
        
        ema = calculate_ema(prices, period)
        
        self.assertIsNone(ema)

    def test_cci_volatility_calculation(self):
        # Test CCI with high volatility data
        price_series = [100, 90, 110, 95, 105, 85, 115] * 2 + [100]  # 15 volatile values
        
        cci, avg_tp, dev, arrow = calculate_cci(price_series)
        
        self.assertIsInstance(cci, float)
        self.assertGreater(dev, 0)  # Should have positive deviation
        self.assertLess(abs(cci), 1000)  # Should be within reasonable bounds

    @patch('indicators.logger')
    def test_calculate_cci_logs_zero_deviation(self, mock_logger):
        price_series = [100] * 15
        
        calculate_cci(price_series)
        
        # Should log warning about zero deviation
        mock_logger.warning.assert_called()

if __name__ == '__main__':
    unittest.main()
