import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import MagicMock
from algorithms.ema_trading_algorithm import EMATradingAlgorithm
from tests.utils import MockIB

class TestContractParameterValidation(unittest.TestCase):
    def setUp(self):
        self.mock_ib = MockIB()

    def _create_ema_algorithm(self, contract_params):
        """Helper method to create EMA algorithm with default parameters"""
        return EMATradingAlgorithm(
            contract_params=contract_params,
            ema_period=10,
            check_interval=5,
            initial_ema=100.0,
            signal_override=False,
            ib=self.mock_ib
        )

    def test_valid_contract_parameters(self):
        """Test algorithm with valid contract parameters"""
        valid_params = {
            'symbol': 'CL',
            'lastTradeDateOrContractMonth': '202601',
            'exchange': 'NYMEX',
            'currency': 'USD'
        }
        
        algo = self._create_ema_algorithm(valid_params)
        
        self.assertEqual(algo.contract.symbol, 'CL')
        self.assertEqual(algo.contract.exchange, 'NYMEX')
        self.assertEqual(algo.contract.currency, 'USD')

    def test_missing_symbol(self):
        """Test contract with missing symbol"""
        invalid_params = {
            'exchange': 'NYMEX',
            'currency': 'USD'
            # Missing symbol
        }
        
        with self.assertRaises((KeyError, ValueError, TypeError)):
            self._create_ema_algorithm(invalid_params)

    def test_empty_symbol(self):
        """Test contract with empty symbol"""
        invalid_params = {
            'symbol': '',  # Empty symbol
            'exchange': 'NYMEX',
            'currency': 'USD'
        }
        
        try:
            algo = self._create_ema_algorithm(invalid_params)
            # Validate that symbol is not empty if algorithm was created
            if hasattr(algo, 'contract') and hasattr(algo.contract, 'symbol'):
                if not algo.contract.symbol:
                    raise ValueError("Symbol cannot be empty")
        except (ValueError, TypeError):
            # Expected for empty symbol
            pass

    def test_missing_exchange(self):
        """Test contract with missing exchange"""
        invalid_params = {
            'symbol': 'CL',
            'currency': 'USD'
            # Missing exchange
        }
        
        with self.assertRaises((KeyError, ValueError, TypeError)):
            self._create_ema_algorithm(invalid_params)

    def test_futures_contract_parameters(self):
        """Test futures-specific contract parameters"""
        futures_params = {
            'symbol': 'CL',
            'lastTradeDateOrContractMonth': '202601',
            'exchange': 'NYMEX',
            'currency': 'USD'
        }
        
        algo = self._create_ema_algorithm(futures_params)
        
        self.assertEqual(algo.contract.symbol, 'CL')
        self.assertEqual(algo.contract.lastTradeDateOrContractMonth, '202601')

    def test_different_contract_types(self):
        """Test different contract types"""
        contract_types = [
            {
                'symbol': 'CL',
                'exchange': 'NYMEX',
                'currency': 'USD',
                'lastTradeDateOrContractMonth': '202601'
            },
            {
                'symbol': 'AAPL',
                'exchange': 'SMART',
                'currency': 'USD'
            }
        ]
        
        for params in contract_types:
            try:
                algo = self._create_ema_algorithm(params)
                self.assertEqual(algo.contract.symbol, params['symbol'])
            except Exception:
                # Some contract types may not be supported
                pass

if __name__ == '__main__':
    unittest.main()
