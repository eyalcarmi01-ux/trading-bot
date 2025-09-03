import unittest
import math
from unittest.mock import MagicMock, patch
from data_fetcher import fetch_initial_data, fetch_close_series, clean_prices_with_previous

class MockBar:
    def __init__(self, high, low, close, open_price=None):
        self.high = high
        self.low = low
        self.close = close
        self.open = open_price or close

class TestDataFetcher(unittest.TestCase):
    def setUp(self):
        self.mock_ib = MagicMock()
        self.mock_contract = MagicMock()

    def test_fetch_initial_data_success(self):
        # Mock successful data retrieval
        mock_bars = [
            MockBar(101, 99, 100),
            MockBar(102, 100, 101),
            MockBar(103, 101, 102)
        ]
        self.mock_ib.reqHistoricalData.return_value = mock_bars
        
        result = fetch_initial_data(self.mock_ib, self.mock_contract)
        
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], 100.0)  # (101+99+100)/3
        self.assertEqual(result[1], 101.0)  # (102+100+101)/3

    def test_fetch_initial_data_empty_response(self):
        self.mock_ib.reqHistoricalData.return_value = []
        
        result = fetch_initial_data(self.mock_ib, self.mock_contract)
        
        self.assertEqual(result, [])

    def test_fetch_initial_data_invalid_values(self):
        mock_bars = [
            MockBar(math.nan, 99, 100),
            MockBar(102, math.inf, 101),
            MockBar(None, 101, 102)
        ]
        self.mock_ib.reqHistoricalData.return_value = mock_bars
        
        result = fetch_initial_data(self.mock_ib, self.mock_contract)
        
        # Should skip invalid bars
        self.assertEqual(len(result), 1)  # Only the third bar should be valid

    def test_fetch_close_series_success(self):
        mock_bars = [
            MockBar(101, 99, 100),
            MockBar(102, 100, 101),
            MockBar(103, 101, 102)
        ]
        self.mock_ib.reqHistoricalData.return_value = mock_bars
        
        result = fetch_close_series(self.mock_ib, self.mock_contract, bars_count=3)
        
        self.assertEqual(result, [100, 101, 102])

    def test_fetch_close_series_with_nan(self):
        mock_bars = [
            MockBar(101, 99, 100),
            MockBar(102, 100, math.nan),
            MockBar(103, 101, 102)
        ]
        self.mock_ib.reqHistoricalData.return_value = mock_bars
        
        result = fetch_close_series(self.mock_ib, self.mock_contract, bars_count=3)
        
        # Should skip NaN values
        self.assertEqual(result, [100, 102])

    def test_clean_prices_with_previous_basic(self):
        prices = [100, 101, None, 103, math.nan, 105]
        
        result = clean_prices_with_previous(prices)
        
        expected = [100, 101, 101, 103, 103, 105]  # None and NaN replaced with previous
        self.assertEqual(result, expected)

    def test_clean_prices_with_previous_empty(self):
        result = clean_prices_with_previous([])
        self.assertEqual(result, [])

    def test_clean_prices_with_previous_all_invalid(self):
        prices = [None, math.nan, None]
        
        result = clean_prices_with_previous(prices)
        
        # Should return empty list if no valid prices
        self.assertEqual(result, [])

    def test_clean_prices_with_previous_starts_invalid(self):
        prices = [None, math.nan, 100, 101]
        
        result = clean_prices_with_previous(prices)
        
        # Should start from first valid price
        self.assertEqual(result, [100, 101])

    @patch('data_fetcher.logger')
    def test_fetch_initial_data_logs_warnings(self, mock_logger):
        mock_bars = [
            MockBar(math.nan, 99, 100),
            MockBar(102, 100, 101)
        ]
        self.mock_ib.reqHistoricalData.return_value = mock_bars
        
        fetch_initial_data(self.mock_ib, self.mock_contract)
        
        # Should log warning for invalid bar
        mock_logger.warning.assert_called()

    @patch('data_fetcher.logger')
    def test_fetch_initial_data_logs_no_data(self, mock_logger):
        self.mock_ib.reqHistoricalData.return_value = []
        
        fetch_initial_data(self.mock_ib, self.mock_contract)
        
        mock_logger.warning.assert_called_with("⚠️ No historical data received.")

    def test_fetch_data_with_exception(self):
        self.mock_ib.reqHistoricalData.side_effect = Exception("Connection error")
        
        with self.assertRaises(Exception):
            fetch_initial_data(self.mock_ib, self.mock_contract)

    def test_fetch_close_series_default_count(self):
        mock_bars = [MockBar(101, 99, i) for i in range(250)]
        self.mock_ib.reqHistoricalData.return_value = mock_bars
        
        result = fetch_close_series(self.mock_ib, self.mock_contract)
        
        # Should default to 200 bars
        self.assertEqual(len(result), 250)

if __name__ == '__main__':
    unittest.main()
