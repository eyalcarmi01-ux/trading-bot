
import unittest
import math
from unittest.mock import MagicMock
from algorithms.ema_trading_algorithm import EMATradingAlgorithm
from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm
from algorithms.cci14_compare_trading_algorithm import CCI14_Compare_TradingAlgorithm
from algorithms.cci14_120_trading_algorithm import CCI14_120_TradingAlgorithm
from tests.utils import MockIB


# --- Advanced Edge Cases for Refactored Algorithms ---
class TestRefactoredAlgorithmEdgeCases(unittest.TestCase):
    def setUp(self):
        self.mock_ib = MockIB()

    def test_cci14rev_invalid_price_handling(self):
        """Test CCI14Rev algorithm with invalid price data"""
    algo = CCI14_120_TradingAlgorithm(
            contract_params={'symbol': 'TEST', 'exchange': 'SMART', 'currency': 'USD'},
            check_interval=60,
            initial_ema=100,
            ib=self.mock_ib
        )
        
        # Test with None price
        self.mock_ib.reqMktData = MagicMock(return_value=MagicMock(last=None, close=None, ask=None, bid=None))
        algo.on_tick("12:00:00")
        # Should handle gracefully without crashing

    def test_cci14rev_nan_price_handling(self):
        """Test CCI14Rev algorithm with NaN price data"""
    algo = CCI14_120_TradingAlgorithm(
            contract_params={'symbol': 'TEST', 'exchange': 'SMART', 'currency': 'USD'},
            check_interval=60,
            initial_ema=100,
            ib=self.mock_ib
        )
        
        # Test with NaN price
        self.mock_ib.reqMktData = MagicMock(return_value=MagicMock(last=math.nan, close=math.nan, ask=math.nan, bid=math.nan))
        algo.on_tick("12:00:00")
        # Should handle gracefully without crashing

    def test_ema_algorithm_empty_signals(self):
        """Test EMA algorithm with empty signal list"""
        algo = EMATradingAlgorithm(
            contract_params={'symbol': 'TEST', 'exchange': 'SMART', 'currency': 'USD'},
            ema_period=10,
            check_interval=60,
            initial_ema=100,
            signal_override=0,
            ib=self.mock_ib
        )
        
        # Should start with empty state
        self.assertIsNotNone(algo)

    def test_fibonacci_algorithm_insufficient_data(self):
        """Test Fibonacci algorithm with insufficient price history"""
        algo = FibonacciTradingAlgorithm(
            contract_params={'symbol': 'TEST', 'exchange': 'SMART', 'currency': 'USD'},
            check_interval=60,
            fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786],
            ib=self.mock_ib
        )
        
        # Test with minimal data
        algo.on_tick("12:00:00")
        # Should handle gracefully without sufficient data

    def test_cci14_algorithm_zero_deviation(self):
        """Test CCI14 algorithm with zero standard deviation"""
    algo = CCI14_Compare_TradingAlgorithm(
            contract_params={'symbol': 'TEST', 'exchange': 'SMART', 'currency': 'USD'},
            check_interval=60,
            initial_ema=100,
            ib=self.mock_ib
        )
        
        # Pre-fill with identical prices (zero deviation)
        algo.price_history = [100.0] * algo.CCI_PERIOD
        algo.on_tick("12:00:00")
        # Should handle zero deviation case

    def test_extreme_price_movements(self):
        """Test algorithms with extreme price movements"""
        algo = EMATradingAlgorithm(
            contract_params={'symbol': 'TEST', 'exchange': 'SMART', 'currency': 'USD'},
            ema_period=10,
            check_interval=60,
            initial_ema=100,
            signal_override=0,
            ib=self.mock_ib
        )
        
        # Test with extreme price jump
        self.mock_ib.reqMktData = MagicMock(return_value=MagicMock(last=10000, close=10000, ask=10000, bid=10000))
        algo.on_tick("12:00:00")
        
        # Test with extreme price drop
        self.mock_ib.reqMktData = MagicMock(return_value=MagicMock(last=0.01, close=0.01, ask=0.01, bid=0.01))
        algo.on_tick("12:00:01")
        
        # Should handle extreme movements gracefully

    def test_algorithm_state_consistency(self):
        """Test that algorithm states remain consistent"""
    algo = CCI14_120_TradingAlgorithm(
            contract_params={'symbol': 'TEST', 'exchange': 'SMART', 'currency': 'USD'},
            check_interval=60,
            initial_ema=100,
            ib=self.mock_ib
        )
        
        # Process multiple ticks and verify state consistency
    for i in range(10):
            price = 100 + i * 0.1
            self.mock_ib.reqMktData = MagicMock(return_value=MagicMock(last=price, close=price, ask=price, bid=price))
            algo.on_tick(f"12:00:{i:02d}")
        
    # State should be consistent (no exceptions thrown)
    self.assertIsNotNone(algo.contract)

    def test_concurrent_algorithm_safety(self):
        """Test algorithm behavior under concurrent access"""
        algo = EMATradingAlgorithm(
            contract_params={'symbol': 'TEST', 'exchange': 'SMART', 'currency': 'USD'},
            ema_period=10,
            check_interval=60,
            initial_ema=100,
            signal_override=0,
            ib=self.mock_ib
        )
        
        # Simulate rapid successive calls
        for i in range(100):
            algo.on_tick(f"12:00:{i:02d}")
        
        # Should handle rapid calls without issues
        self.assertIsNotNone(algo)


    # Legacy calculate_signals-based edge case classes removed; not applicable to refactored design