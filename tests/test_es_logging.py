import os
import sys
import types
import unittest

from tests.utils import MockIB, MockPosition
from algorithms.trading_algorithms_class import TradingAlgorithm


class TestESTradeLogging(unittest.TestCase):
    def setUp(self):
        # Enable ES logging via env and inject a fake es_client module
        self._old_enabled = os.environ.get('TRADES_ES_ENABLED')
        self._old_index = os.environ.get('TRADES_ES_INDEX')
        os.environ['TRADES_ES_ENABLED'] = '1'
        os.environ['TRADES_ES_INDEX'] = 'test_trades'

        self._prev_es_module = sys.modules.get('es_client')
        self.docs = []

        fake = types.ModuleType('es_client')

        def get_es_client(url=None):
            return object()

        def ensure_index(client, index, mappings=None):
            return True

        def index_doc(client, index, doc):
            # Capture indexed docs for assertions
            self.docs.append(doc)

        fake.get_es_client = get_es_client
        fake.ensure_index = ensure_index
        fake.index_doc = index_doc
        sys.modules['es_client'] = fake

    def tearDown(self):
        # Restore env vars
        if self._old_enabled is None:
            os.environ.pop('TRADES_ES_ENABLED', None)
        else:
            os.environ['TRADES_ES_ENABLED'] = self._old_enabled
        if self._old_index is None:
            os.environ.pop('TRADES_ES_INDEX', None)
        else:
            os.environ['TRADES_ES_INDEX'] = self._old_index

        # Restore es_client module
        if self._prev_es_module is None:
            sys.modules.pop('es_client', None)
        else:
            sys.modules['es_client'] = self._prev_es_module

    def _make_algo(self):
    params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
    ib = MockIB()
    algo = TradingAlgorithm(contract_params=params, ib=ib)
    return algo, ib

    def test_logs_enter_on_bracket(self):
        algo, _ = self._make_algo()
        # Place a simple BUY bracket with predictable prices from MockIB (100.0)
        algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)

        # Expect at least one ES doc for entry
        self.assertGreaterEqual(len(self.docs), 1)
        enter = self.docs[0]
        self.assertEqual(enter.get('event'), 'enter')
        self.assertEqual(enter.get('action'), 'BUY')
        self.assertEqual(enter.get('quantity'), 1)
        self.assertAlmostEqual(enter.get('price'), 100.0, places=4)
        self.assertEqual(enter.get('algo'), 'TradingAlgorithm')
        self.assertEqual(enter.get('symbol'), 'CL')

    def test_logs_exit_on_tp_fill_with_pnl(self):
        algo, ib = self._make_algo()
        algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)
        # Clear any entry doc to focus on exit event
        self.docs.clear()

        # Simulate a TP fill trade
        tp_id = algo._last_tp_id

        class OS:
            status = 'Filled'

        class TR:
            def __init__(self, oid):
                self.order = types.SimpleNamespace(orderId=oid)
                self.orderStatus = OS()

        ib._trades = [TR(tp_id)]
        algo._check_fills_and_reset_state()

        # Expect one ES doc for exit with TP reason and correct PnL (0.10)
        self.assertGreaterEqual(len(self.docs), 1)
        exit_doc = self.docs[0]
        self.assertEqual(exit_doc.get('event'), 'exit')
        self.assertEqual(exit_doc.get('reason'), 'TP')
        self.assertIn('pnl', exit_doc)
        self.assertAlmostEqual(exit_doc.get('pnl', 0.0), 0.10, places=4)

    def test_logs_exit_on_sl_fill_with_pnl(self):
        algo, ib = self._make_algo()
        algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)
        # Clear entry doc(s)
        self.docs.clear()

        # Simulate an SL fill
        sl_id = algo._last_sl_id

        class OS:
            status = 'Filled'

        class TR:
            def __init__(self, oid):
                self.order = types.SimpleNamespace(orderId=oid)
                self.orderStatus = OS()

        ib._trades = [TR(sl_id)]
        algo._check_fills_and_reset_state()

        # Expect exit doc with SL reason and negative PnL (-0.07)
        self.assertGreaterEqual(len(self.docs), 1)
        exit_doc = self.docs[0]
        self.assertEqual(exit_doc.get('event'), 'exit')
        self.assertEqual(exit_doc.get('reason'), 'SL')
        self.assertIn('pnl', exit_doc)
        self.assertAlmostEqual(exit_doc.get('pnl', 0.0), -0.07, places=4)

    def test_logs_exit_on_sl_breach_manual_close_with_pnl(self):
        algo, ib = self._make_algo()
        # Place a BUY bracket to set entry context (entry_ref_price, qty sign)
        algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)
        self.docs.clear()

        # Set an SL that is above market to trigger breach for a LONG position
        algo.current_sl_price = 100.5
        positions = [MockPosition(algo.contract, position=1)]

        # Trigger stop monitoring which will execute manual close path
        algo._monitor_stop(positions)

        # Expect an exit doc with SL_breach reason and computed PnL (0.0 here)
        self.assertGreaterEqual(len(self.docs), 1)
        exit_doc = self.docs[0]
        self.assertEqual(exit_doc.get('event'), 'exit')
        self.assertEqual(exit_doc.get('reason'), 'SL_breach')
        self.assertIn('pnl', exit_doc)
        self.assertAlmostEqual(exit_doc.get('pnl', 1.0) , 0.0, places=4)

    def test_entry_doc_includes_indicators(self):
        algo, _ = self._make_algo()
        # Provide indicator snapshots before entry
        algo._multi_emas = {10: 99.8, 20: 99.5, 50: 98.9}
        algo.cci_values = [-127.4]

        algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)

        self.assertGreaterEqual(len(self.docs), 1)
        enter = self.docs[0]
        self.assertEqual(enter.get('event'), 'enter')
        emas = enter.get('emas') or {}
        self.assertTrue(all(k in emas for k in ('EMA10', 'EMA20', 'EMA50')))
        self.assertIsInstance(emas['EMA10'], float)
        self.assertIsInstance(emas['EMA20'], float)
        self.assertIsInstance(emas['EMA50'], float)
        self.assertAlmostEqual(enter.get('cci', 0.0), -127.4, places=1)

    def test_disabled_es_logging_no_docs(self):
        # Temporarily disable ES logging and instantiate a new algo
        os.environ['TRADES_ES_ENABLED'] = '0'
        algo, _ = self._make_algo()
        self.docs.clear()
        algo.place_bracket_order('BUY', 1, 0.01, 7, 10, 10)
        # Expect no docs captured when disabled
        self.assertEqual(len(self.docs), 0)


if __name__ == '__main__':
    unittest.main()
