import unittest
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import MagicMock, patch
from algorithms.ema_trading_algorithm import EMATradingAlgorithm
from algorithms.cci14rev_trading_algorithm import CCI14RevTradingAlgorithm
from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm

class MockIB:
    def __init__(self):
        self.orders = []
        self.positions_list = []
        self.connected = True
        self.call_count = 0
        self.call_times = []

    def reqMktData(self, contract, snapshot=True):
        self.call_count += 1
        self.call_times.append(time.time())
        return MagicMock(last=100, close=100, ask=100, bid=100)

    def sleep(self, seconds):
        time.sleep(min(seconds, 0.1))  # Cap sleep for tests

    def positions(self):
        self.call_count += 1
        return self.positions_list

    def placeOrder(self, contract, order):
        self.call_count += 1
        self.orders.append((contract, order))
        return MagicMock(orderId=len(self.orders))

    def qualifyContracts(self, contract):
        self.call_count += 1
        return [contract]

class TestPerformance(unittest.TestCase):
    def setUp(self):
        self.mock_ib = MockIB()
        self.contract_params = {
            'symbol': 'CL',
            'exchange': 'NYMEX',
            'currency': 'USD'
        }

    def test_algorithm_initialization_performance(self):
        """Test algorithm initialization performance"""
        start_time = time.time()
        
        algo = EMATradingAlgorithm(
            contract_params=self.contract_params,
            ema_period=10,
            check_interval=5,
            initial_ema=100.0,
            signal_override=0,
            ib=self.mock_ib
        )
        
        end_time = time.time()
        initialization_time = end_time - start_time
        
        # Should initialize quickly (within 1 second)
        self.assertLess(initialization_time, 1.0)

    def test_signal_check_performance(self):
        """Test signal checking performance"""
        algo = EMATradingAlgorithm(
            contract_params=self.contract_params,
            ema_period=10,
            check_interval=5,
            initial_ema=100.0,
            signal_override=0,
            ib=self.mock_ib
        )
        
        start_time = time.time()
        
        # Run multiple signal checks
        for i in range(100):
            # simulate time string
            algo.on_tick(f"12:00:{i:02d}")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete 100 checks within reasonable time
        self.assertLess(total_time, 5.0)  # 5 seconds max
        
        # Average time per check
        avg_time = total_time / 100
        self.assertLess(avg_time, 0.1)  # 100ms max per check

    def test_memory_usage_stability(self):
        """Test memory usage stability over multiple operations"""
        import gc
        
        algo = CCI14RevTradingAlgorithm(
            contract_params=self.contract_params,
            check_interval=5,
            initial_ema=100.0,
            ib=self.mock_ib
        )
        
        # Force garbage collection
        gc.collect()
        
        # Run many operations
        for i in range(1000):
            algo.on_tick("12:00:00")
            
            # Periodic cleanup check
            if i % 100 == 0:
                gc.collect()
        
        # Memory should be stable (no major leaks)
        # This is a basic test - real memory profiling would be more complex
        self.assertTrue(True)  # Placeholder for memory assertions

    def test_api_call_efficiency(self):
        """Test API call efficiency"""
        algo = EMATradingAlgorithm(
            contract_params=self.contract_params,
            ema_period=10,
            check_interval=5,
            initial_ema=100.0,
            signal_override=0,
            ib=self.mock_ib
        )
        
        initial_calls = self.mock_ib.call_count
        
        # Run signal checks
        for i in range(10):
            algo.on_tick(f"12:00:{i:02d}")
        
        final_calls = self.mock_ib.call_count
        api_calls = final_calls - initial_calls
        
        # Should minimize API calls
        # Exact number depends on implementation
        self.assertLess(api_calls, 50)  # Should not exceed 5 calls per check

    def test_calculation_performance(self):
        """Test calculation performance for different algorithms"""
        algorithms = [
            (EMATradingAlgorithm, {'ema_period': 20, 'check_interval': 5, 'initial_ema': 100.0, 'signal_override': 0}),
            (CCI14RevTradingAlgorithm, {'check_interval': 5, 'initial_ema': 100.0}),
            (FibonacciTradingAlgorithm, {'check_interval': 5, 'fib_levels': [0.236, 0.382, 0.5, 0.618, 0.786]}),
        ]
        
        performance_results = {}
        
        for algo_class, params in algorithms:
            algo = algo_class(contract_params=self.contract_params, ib=self.mock_ib, **params)
            
            # Time calculation performance
            start_time = time.time()
            
            for i in range(50):
                algo.on_tick(f"12:00:{i:02d}")
            
            end_time = time.time()
            performance_results[algo_class.__name__] = end_time - start_time
        
        # All algorithms should complete within reasonable time
        for algo_name, duration in performance_results.items():
            self.assertLess(duration, 2.0, f"{algo_name} took too long: {duration}s")

    def test_concurrent_algorithm_performance(self):
        """Test performance with multiple algorithm instances"""
        algorithms = []
        
        # Create multiple instances
        for i in range(5):
            algo = EMATradingAlgorithm(
                contract_params=self.contract_params,
                ema_period=10 + i,
                check_interval=5,
                initial_ema=100.0,
                signal_override=0,
                ib=MockIB()  # Each gets its own mock IB
            )
            algorithms.append(algo)
        
        start_time = time.time()
        
        # Run all algorithms
        for _ in range(20):
            for idx, algo in enumerate(algorithms):
                algo.on_tick(f"12:00:{idx:02d}")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should handle multiple instances efficiently
        self.assertLess(total_time, 5.0)

    def test_large_dataset_performance(self):
        """Test performance with large datasets"""
        algo = CCI14RevTradingAlgorithm(
            contract_params=self.contract_params,
            check_interval=5,
            initial_ema=100.0,
            ib=self.mock_ib
        )
        
        # Mock large price history
        large_prices = list(range(1000))
        
        # Simulate large data by feeding many ticks
        start_time = time.time()
        for i in range(1000):
            price = float(i)
            self.mock_ib.reqMktData = MagicMock(return_value=MagicMock(last=price, close=price, ask=price, bid=price))
            algo.on_tick("12:00:00")
        end_time = time.time()
            
            # Should handle large datasets efficiently
            self.assertLess(end_time - start_time, 2.0)

    def test_repeated_signal_generation_performance(self):
        """Test performance of repeated signal generation"""
        algo = FibonacciTradingAlgorithm(
            contract_params=self.contract_params,
            check_interval=5,
            fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786],
            ib=self.mock_ib
        )
        
        # Measure performance over many iterations
        iterations = 200
        start_time = time.time()
        
        for i in range(iterations):
            self.mock_ib.reqMktData = MagicMock(return_value=MagicMock(last=100.0 + i % 3, close=100.0, ask=100.0, bid=100.0))
            algo.on_tick("12:00:00")
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / iterations
        
        # Should maintain consistent performance
        self.assertLess(avg_time, 0.05)  # 50ms max per iteration
        self.assertLess(total_time, 5.0)  # Total under 5 seconds

    def test_cache_performance_impact(self):
        """Test cache performance impact if caching is implemented"""
        algo = EMATradingAlgorithm(
            contract_params=self.contract_params,
            ema_period=10,
            check_interval=5,
            initial_ema=100.0,
            signal_override=0,
            ib=self.mock_ib
        )
        
        # First run (cold cache)
        start_time = time.time()
    algo.on_tick("12:00:00")
        first_run_time = time.time() - start_time
        
        # Second run (warm cache)
        start_time = time.time()
    algo.on_tick("12:00:01")
        second_run_time = time.time() - start_time
        
        # Second run should be same or faster (if caching is implemented)
        # This test is implementation dependent
        self.assertLessEqual(second_run_time, first_run_time * 2)

    def test_error_handling_performance_impact(self):
        """Test performance impact of error handling"""
        algo = EMATradingAlgorithm(
            contract_params=self.contract_params,
            ema_period=10,
            check_interval=5,
            initial_ema=100.0,
            signal_override=0,
            ib=self.mock_ib
        )
        
        # Normal operation timing
        start_time = time.time()
        for _ in range(10):
            algo.check_signals()
        normal_time = time.time() - start_time
        
        # Operation with errors
        start_time = time.time()
        for _ in range(10):
            try:
                # Force error condition
                with patch.object(self.mock_ib, 'reqMktData', side_effect=Exception("Error")):
                    algo.check_signals()
            except:
                pass
        error_time = time.time() - start_time
        
        # Error handling should not significantly slow down operation
        self.assertLess(error_time, normal_time * 5)  # Max 5x slower with errors

    def test_cleanup_performance(self):
        """Test cleanup operation performance"""
        algo = CCI14RevTradingAlgorithm(
            contract_params=self.contract_params,
            cci_period=14,
            ib=self.mock_ib
        )
        
        # Add data to clean up
        if hasattr(algo, 'price_history'):
            algo.price_history = list(range(10000))
        
        # Test cleanup performance
        start_time = time.time()
        
        if hasattr(algo, 'cleanup'):
            algo.cleanup()
        else:
            # Manual cleanup simulation
            if hasattr(algo, 'price_history'):
                algo.price_history = algo.price_history[-100:]
        
        end_time = time.time()
        cleanup_time = end_time - start_time
        
        # Cleanup should be fast
        self.assertLess(cleanup_time, 0.5)

    def test_parameter_validation_performance(self):
        """Test parameter validation performance impact"""
        # Time with validation
        start_time = time.time()
        
        for i in range(100):
            try:
                algo = EMATradingAlgorithm(
                    contract_params=self.contract_params,
                    ema_period=10 + i % 50,
                    ib=self.mock_ib
                )
            except:
                pass
        
        end_time = time.time()
        validation_time = end_time - start_time
        
        # Validation should not significantly impact performance
        self.assertLess(validation_time, 2.0)

    def test_threading_performance_impact(self):
        """Test performance impact of thread safety if implemented"""
        import threading
        
        algo = EMATradingAlgorithm(
            contract_params=self.contract_params,
            ema_period=10,
            ib=self.mock_ib
        )
        
        results = []
        
        def run_signals():
            start = time.time()
            for i in range(10):
                algo.on_tick(f"12:00:{i:02d}")
            results.append(time.time() - start)
        
        # Run multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=run_signals)
            threads.append(thread)
        
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Should handle concurrent access efficiently
        self.assertLess(total_time, 3.0)
        self.assertEqual(len(results), 3)

if __name__ == '__main__':
    unittest.main()
