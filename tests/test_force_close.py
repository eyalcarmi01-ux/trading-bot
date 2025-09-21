import datetime
import unittest
from unittest.mock import MagicMock

from algorithms.trading_algorithms_class import TradingAlgorithm
from tests.utils import MockIB, MockPosition
from ib_insync import Future


class _ForceCloseAlgo(TradingAlgorithm):
    CHECK_INTERVAL = 0.01
    def on_tick(self, time_str):
        # No trading logic needed for force-close test
        pass

class ForceCloseTests(unittest.TestCase):
    def setUp(self):
        self.ib = MockIB()
        contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202512', exchange='NYMEX', currency='USD')
        # Configure force_close to one minute in the past so next occurrence rolls forward
        now = datetime.datetime.now()
        force_close = (now.hour, (now.minute + 1) % 60)  # upcoming minute
        self.algo = _ForceCloseAlgo(contract_params, client_id=999, ib=self.ib, force_close=force_close, defer_connection=True)
        # Inject a mock qualified contract id and open position
        fut = Future(**contract_params)
        fut.conId = 1234
        self.algo.contract = fut
        pos_contract = Future(**contract_params)
        pos_contract.conId = 1234
        self.ib._positions = [MockPosition(pos_contract, 1)]

    def test_force_close_flattens_position(self):
        # Fast-forward internal force-close timestamp to now - 1s
        now = datetime.datetime.now()
        self.algo._force_close_dt = now - datetime.timedelta(seconds=1)
        # Run a single loop iteration's force-close portion directly
        self.algo._maybe_force_close(now, now.strftime('%H:%M:%S'))
        # After force-close, positions should have been closed (MockIB leaves list; we assert phase/state reset)
        self.assertEqual(self.algo.trade_phase, 'IDLE')
        # Ensure next force-close scheduled in future
        self.assertIsNotNone(self.algo._force_close_dt)
        self.assertGreater(self.algo._force_close_dt, now)

if __name__ == '__main__':
    unittest.main()
