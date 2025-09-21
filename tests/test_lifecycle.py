import unittest
from unittest.mock import MagicMock

from algorithms.trading_algorithms_class import TradingAlgorithm
from tests.utils import MockIB, MockPosition


class TestLifecyclePhases(unittest.TestCase):
    def setUp(self):
        self.ib = MockIB()
        params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
        self.algo = TradingAlgorithm(contract_params=params, ib=self.ib)
        # Stable market data
        self.ib.reqMktData = MagicMock(return_value=MagicMock(last=100.0, close=100.0, ask=100.0, bid=100.0))
        # Ensure contract has a conId for position tracking
        try:
            self.algo.contract.conId = 1
        except Exception:
            pass
        self.transitions = []
        original_set = self.algo._set_trade_phase

        def recording_set(phase, **kw):
            before = getattr(self.algo, 'trade_phase', None)
            original_set(phase, **kw)
            after = getattr(self.algo, 'trade_phase', None)
            if before != after:
                self.transitions.append((before, after))
        self.algo._set_trade_phase = recording_set

    def test_bracket_order_phase_sequence(self):
        # Simulate a signal ready state
        self.algo._set_trade_phase('SIGNAL_PENDING', reason='Test setup')
        # Place bracket
        self.algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)
        # Final phase should be ACTIVE
        self.assertEqual(self.algo.trade_phase, 'ACTIVE')
        self.assertEqual(self.algo.current_direction, 'LONG')
        # We expect SIGNAL_PENDING -> BRACKET_SENT -> ACTIVE (ACTIVE may replace BRACKET_SENT quickly)
        self.assertIn(('SIGNAL_PENDING', 'BRACKET_SENT'), self.transitions)
        self.assertIn(('BRACKET_SENT', 'ACTIVE'), self.transitions)

    def test_stop_loss_breach_phase_sequence(self):
        # Prepare an active long position with an SL above market that will be breached
        self.ib._positions = [MockPosition(self.algo.contract, 1)]
        self.algo.current_sl_price = 101.0  # market is 100 -> breach for LONG (price <= SL)
        self.algo.current_direction = 'LONG'
        # Trigger monitor_stop
        self.algo._monitor_stop(self.ib.positions())
        # Verify full EXITING->CLOSED->IDLE cycle
        expected = [
            ('IDLE', 'EXITING'),
            ('EXITING', 'CLOSED'),
            ('CLOSED', 'IDLE'),
        ]
        for pair in expected:
            self.assertIn(pair, self.transitions)
        self.assertEqual(self.algo.trade_phase, 'IDLE')
        self.assertIsNone(self.algo.current_direction)
        self.assertIsNone(self.algo.current_sl_price)


if __name__ == '__main__':
    unittest.main()
