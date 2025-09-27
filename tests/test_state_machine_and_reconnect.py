import unittest
from unittest.mock import MagicMock, patch
from algorithms.trading_algorithms_class import TradingAlgorithm

class TestStateMachineAndReconnect(unittest.TestCase):
    def setUp(self):
        # Minimal contract params for instantiation
        self.contract_params = {
            'symbol': 'ES',
            'exchange': 'GLOBEX',
            'currency': 'USD'
        }
        self.algo = TradingAlgorithm(self.contract_params, ib=MagicMock())
        self.algo._lock = MagicMock()  # Patch lock for thread safety

    def test_preserve_blocking_states_on_exception(self):
        # Test that exception handler does not reset to IDLE if in blocking state
        for state in ['ORDER_PLACING', 'BRACKET_SENT', 'ACTIVE', 'EXITING']:
            self.algo.trade_phase = state
            with patch.object(self.algo, 'reset_state') as mock_reset_state:
                with patch.object(self.algo, 'reconnect') as mock_reconnect:
                    self.algo._handle_loop_exception(Exception('Test'))
                    self.assertEqual(self.algo.trade_phase, state)

    def test_reset_to_idle_on_safe_state(self):
        # Test that exception handler resets to IDLE if not in blocking state
        for state in ['IDLE', 'CLOSED', None]:
            self.algo.trade_phase = state
            with patch.object(self.algo, 'reset_state') as mock_reset_state:
                with patch.object(self.algo, 'reconnect') as mock_reconnect:
                    self.algo._handle_loop_exception(Exception('Test'))
                    self.assertEqual(self.algo.trade_phase, 'IDLE')

    def test_no_double_wait_at_startup(self):
        # Patch _main_loop to check timing
        with patch.object(self.algo, '_main_loop') as mock_main_loop:
            with patch.object(self.algo, 'log'):
                with patch.object(self.algo, '_wait_for_round_minute') as mock_wait:
                    self.algo.run()
                    mock_wait.assert_not_called()  # Should not be called in run()
                    mock_main_loop.assert_called_once()

if __name__ == '__main__':
    unittest.main()
