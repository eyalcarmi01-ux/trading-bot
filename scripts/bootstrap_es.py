#!/usr/bin/env python3
"""Bootstrap Elasticsearch: create a default index and ingest a sample doc.

Usage:
  python scripts/bootstrap_es.py [index_name]
"""
from __future__ import annotations
import sys
from datetime import datetime, timezone

import os
import sys as _sys
_sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from es_client import get_es_client, ensure_index, index_doc


def main() -> int:
    index = sys.argv[1] if len(sys.argv) > 1 else "trading-bot-logs"
    es = get_es_client()
    if es is None:
        print("Elasticsearch client not installed. Run: pip install elasticsearch>=8")
        return 1
    ensure_index(es, index, mappings={
        "properties": {
            "timestamp": {"type": "date"},
            "algo": {"type": "keyword"},
            "level": {"type": "keyword"},
            "message": {"type": "text"},
        }
    })
    doc = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "algo": "bootstrap",
        "level": "INFO",
        "message": "Elasticsearch bootstrap successful",
    }
    res = index_doc(es, index, doc)
    print(f"Indexed bootstrap doc to {index}: {res.get('_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
