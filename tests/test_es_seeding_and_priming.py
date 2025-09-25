import unittest
from unittest.mock import MagicMock

from algorithms.trading_algorithms_class import TradingAlgorithm


class FakeAlgo(TradingAlgorithm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Force-enable ES logging with a fake client
        self.enable_es_logging = True
        class _FakeES:
            def __init__(self):
                self.docs = []
            def index_doc(self, client, index, doc):
                # mimic es_client.index_doc wrapper API
                self.docs.append((index, doc))
        # monkey-patch es_client helpers used by base
        self._es_client = object()
        self._es_index = "test-index"
        # patch module-level functions via instance attributes used in base
        # The base calls into es_client via imported module 'es_client' as _es
        import es_client as _es
        self._es_mod = _es
        # stub get_es_client and ensure_index
        _es.get_es_client = MagicMock(return_value=self._es_client)
        _es.ensure_index = MagicMock()
        _es.index_doc = MagicMock()
        _es.bulk_index = MagicMock()

    # Minimal abstract method implementations if required by base
    def on_tick(self, tick):
        pass


class TestESSeedingPriming(unittest.TestCase):
    def setUp(self):
        self.algo = FakeAlgo(name="TestAlgo", symbol="ES", contract={"symbol": "ES"})

    def test_seed_and_priming_docs_indexed(self):
        # Prepare deterministic bars for seeding (3 bars)
        bars = [
            {"timestamp": 1000, "close": 10.0},
            {"timestamp": 2000, "close": 20.0},
            {"timestamp": 3000, "close": 30.0},
        ]

        # Spy on es_client.index_doc to capture documents
        import es_client as _es
        captured = []
        def capture_index_doc(client, index, doc):
            captured.append(doc)
        _es.index_doc.side_effect = capture_index_doc

        # Execute: simulate seed export and priming export
        self.algo._es_prepare()  # ensure mapping call path works
        self.algo._es_log_seed_history(bars)
        # pick first two closes as priming used sample
        self.algo._es_log_priming_used([10.0, 20.0])

        # Assertions: two documents emitted: seed and priming
        events = [doc.get("event") for doc in captured]
        self.assertIn("seed", events)
        self.assertIn("priming", events)

        # Verify seed doc shape
        seed_docs = [d for d in captured if d.get("event") == "seed"]
        self.assertEqual(len(seed_docs), 1)
        seed = seed_docs[0]
    self.assertEqual(seed.get("algo"), "TestAlgo")
    self.assertIn("contract", seed)
    self.assertEqual(seed.get("contract", {}).get("symbol"), "ES")
        history = seed.get("history")
        self.assertEqual(len(history), 3)
        # order and fields
        self.assertEqual(history[0]["index"], 0)
        self.assertEqual(history[0]["timestamp"], 1000)
        self.assertEqual(history[0]["close"], 10.0)

        # Verify priming doc shape
        prim_docs = [d for d in captured if d.get("event") == "priming"]
        self.assertEqual(len(prim_docs), 1)
        prim = prim_docs[0]
        priming = prim.get("priming")
        self.assertEqual(len(priming), 2)
        self.assertEqual(priming[0]["index"], 0)
        self.assertEqual(priming[0]["close"], 10.0)

    def test_es_disabled_emits_nothing(self):
        import es_client as _es
        _es.index_doc.reset_mock()
        self.algo.enable_es_logging = False
        self.algo._es_log_seed_history([{"timestamp": 1, "close": 1.0}])
        self.algo._es_log_priming_used([1.0])
        _es.index_doc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
