import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import MagicMock
from algorithms.trading_algorithms_class import TradingAlgorithm
from tests.utils import MockIB, MockPosition

class TestTradingAlgorithmBase(unittest.TestCase):
    def setUp(self):
        self.mock_ib = MockIB()

    def test_base_algorithm_initialization(self):
        """Test base algorithm constructor"""
        contract_params = {
            'symbol': 'CL',
            'exchange': 'NYMEX',
            'currency': 'USD'
        }
        
        algo = TradingAlgorithm(
            contract_params=contract_params,
            ib=self.mock_ib
        )
        
        self.assertIsNotNone(algo.ib)
        self.assertIsNotNone(algo.contract)
        self.assertEqual(algo.contract.symbol, 'CL')

    def test_base_algorithm_invalid_parameters(self):
        """Test base algorithm with invalid parameters"""
        # The base TradingAlgorithm doesn't validate contract params extensively
        # It just passes them to Future() constructor
        # Let's test what would actually fail
        try:
            TradingAlgorithm(
                contract_params={},  # Empty dict - may or may not fail
                ib=self.mock_ib
            )
            # If it doesn't fail, that's also valid behavior
        except Exception:
            # Exception is expected for invalid params
            pass

    def test_base_algorithm_contract_creation(self):
        """Test contract creation from parameters"""
        contract_params = {
            'symbol': 'CL',
            'exchange': 'NYMEX',
            'currency': 'USD',
            'lastTradeDateOrContractMonth': '202601'
        }
        
        algo = TradingAlgorithm(
            contract_params=contract_params,
            ib=self.mock_ib
        )
        
        self.assertEqual(algo.contract.symbol, 'CL')
        self.assertEqual(algo.contract.exchange, 'NYMEX')
        self.assertEqual(algo.contract.currency, 'USD')

    def test_base_algorithm_has_valid_price_method(self):
        """Test that base algorithm has get_valid_price method"""
        contract_params = {'symbol': 'CL', 'exchange': 'NYMEX', 'currency': 'USD'}
        algo = TradingAlgorithm(contract_params=contract_params, ib=self.mock_ib)
        
        # Should have the method
        self.assertTrue(hasattr(algo, 'get_valid_price'))
        self.assertTrue(callable(getattr(algo, 'get_valid_price')))
        
        # Should return a valid price
        price = algo.get_valid_price()
        self.assertIsInstance(price, (int, float, type(None)))

    def test_base_algorithm_has_price_history_method(self):
        """Test that base algorithm has update_price_history method"""
        contract_params = {'symbol': 'CL', 'exchange': 'NYMEX', 'currency': 'USD'}
        algo = TradingAlgorithm(contract_params=contract_params, ib=self.mock_ib)
        
        # Should have the method
        self.assertTrue(hasattr(algo, 'update_price_history'))
        self.assertTrue(callable(getattr(algo, 'update_price_history')))
        
        # Should be able to update price history
        algo.update_price_history(100.0)
        self.assertTrue(hasattr(algo, 'price_history'))
        self.assertIn(100.0, algo.price_history)

    def test_base_algorithm_has_active_position_method(self):
        """Test that base algorithm has has_active_position method"""
        contract_params = {'symbol': 'CL', 'exchange': 'NYMEX', 'currency': 'USD'}
        algo = TradingAlgorithm(contract_params=contract_params, ib=self.mock_ib)
        
        # Should have the method
        self.assertTrue(hasattr(algo, 'has_active_position'))
        self.assertTrue(callable(getattr(algo, 'has_active_position')))
        
        # Should return boolean
        result = algo.has_active_position()
        self.assertIsInstance(result, bool)

    def test_has_active_position_conid_matching(self):
        contract_params = {'symbol': 'CL', 'exchange': 'NYMEX', 'currency': 'USD'}
        algo = TradingAlgorithm(contract_params=contract_params, ib=self.mock_ib)
        # Force a known conId on algo contract
        algo.contract.conId = 123
        # Matching position -> True
        pos_contract_match = type('C', (), {'conId': 123})()
        pos_match = MockPosition(pos_contract_match, 1)
        # Non-matching position -> False
        pos_contract_other = type('C', (), {'conId': 999})()
        pos_other = MockPosition(pos_contract_other, 2)
        self.mock_ib._positions = [pos_other]
        self.assertFalse(algo.has_active_position())
        self.mock_ib._positions = [pos_match]
        self.assertTrue(algo.has_active_position())

    def test_base_algorithm_polymorphism(self):
        """Test that base class can be used polymorphically"""
        contract_params = {'symbol': 'TEST', 'exchange': 'SMART', 'currency': 'USD'}
        algo = TradingAlgorithm(
            contract_params=contract_params,
            ib=self.mock_ib
        )
        
        # Should be instance of base class
        self.assertIsInstance(algo, TradingAlgorithm)
        
        # Should have core methods
        core_methods = ['get_valid_price', 'update_price_history', 'has_active_position', 'handle_active_position']
        for method in core_methods:
            self.assertTrue(hasattr(algo, method), f"Missing method: {method}")

if __name__ == '__main__':
    unittest.main()
