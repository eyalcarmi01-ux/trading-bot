#!/usr/bin/env python3
"""Ensure the trades_seed index exists with the correct mapping and insert a test doc.

Usage:
  python scripts/ensure_trades_seed.py [index_name]

This uses the same mapping as algorithms/trading_algorithms_class.py::_es_prepare_seed.
"""
from __future__ import annotations
import os
import sys
from datetime import datetime, timezone

# Ensure local imports work when run directly
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from es_client import get_es_client, ensure_index, index_doc

SEED_MAPPING = {
    "properties": {
        "timestamp": {"type": "date"},
        "algo": {"type": "keyword"},
        "event": {"type": "keyword"},
        "history": {
            "type": "nested",
            "properties": {
                "index": {"type": "integer"},
                "timestamp": {"type": "keyword"},
                "close": {"type": "double"}
            }
        },
        "priming": {
            "type": "nested",
            "properties": {
                "index": {"type": "integer"},
                "close": {"type": "double"}
            }
        },
        "contract": {
            "type": "object",
            "properties": {
                "symbol": {"type": "keyword"},
                "expiry": {"type": "keyword"},
                "exchange": {"type": "keyword"},
                "currency": {"type": "keyword"},
                "localSymbol": {"type": "keyword"},
                "secType": {"type": "keyword"},
                "multiplier": {"type": "keyword"},
                "tradingClass": {"type": "keyword"},
                "conId": {"type": "long"}
            }
        }
    }
}


def main() -> int:
    index = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TRADES_ES_SEED_INDEX", "trades_seed")
    es = get_es_client()
    if es is None:
        print("Elasticsearch client not installed. Run: pip install elasticsearch>=8")
        return 1

    ensure_index(es, index, mappings=SEED_MAPPING)

    doc = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "algo": "seed_probe",
        "event": "priming",
        "priming": [{"index": 1, "close": 123.45}, {"index": 2, "close": 123.55}],
        "contract": {"symbol": "TEST", "exchange": "SMART", "currency": "USD"}
    }
    res = index_doc(es, index, doc)
    print(f"Indexed seed probe to {index}: {res.get('_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
