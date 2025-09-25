#!/usr/bin/env python3
"""
Seed Elasticsearch with dummy trade documents and print sample results.

Usage:
    python scripts/seed_trades_es.py [--if-empty] [--force] [index_name]
    python scripts/seed_trades_es.py --preview    # print docs without indexing (works without ES)

Requires: elasticsearch>=8, a local ES at $ES_URL (default http://localhost:9200)
"""
from __future__ import annotations
import sys
import time
from datetime import datetime, timezone, timedelta
from pprint import pprint

import os
import sys as _sys
# Ensure project root is on sys.path when running as a script
_sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from es_client import get_es_client, ensure_index, bulk_index

TRADE_MAPPING = {
    "properties": {
        "timestamp": {"type": "date"},
        "algo": {"type": "keyword"},
        "action": {"type": "keyword"},
    "entry_action": {"type": "keyword"},
    "exit_action": {"type": "keyword"},
        "quantity": {"type": "integer"},  # +1 for BUY, -1 for SELL
        "price": {"type": "double"},
        "event": {"type": "keyword"},  # enter | exit
        "reason": {"type": "keyword"},  # TP_fill | SL_fill | SL_breach | manual | etc.
        "pnl": {"type": "double"},
        "emas": {"type": "object", "enabled": True},
        "cci": {"type": "double"},
        "contract": {
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
        },
    }
}

def wait_for_es(es, timeout_sec: float = 20.0) -> None:
    """Wait for ES to be reachable and cluster to be at least yellow."""
    deadline = time.time() + timeout_sec
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            # Touch info and cluster health
            es.info()
            health = es.cluster.health(wait_for_status="yellow", timeout="5s")
            if health and health.get("status") in {"yellow", "green"}:
                return
        except Exception as e:  # pragma: no cover - best effort
            last_err = e
            time.sleep(1)
    if last_err:
        raise last_err

def build_dummy_docs(now: datetime) -> list[dict]:
    """Create a small set of enter/exit pairs with indicators and PnL."""
    docs: list[dict] = []
    base = now - timedelta(minutes=5)

    def trade_pair(algo: str, symbol: str, side: str, entry: float, exit_: float, emas: dict, cci: float, reason: str, contract: dict | None = None):
        side_u = side.upper()
        qty_sign = +1 if side_u == "BUY" else -1
        exit_side = "SELL" if side_u == "BUY" else "BUY"
        contract = contract or {"symbol": symbol, "expiry": "202601", "exchange": "NYMEX", "currency": "USD", "localSymbol": f"{symbol}FUT", "secType": "FUT", "multiplier": "1000", "tradingClass": symbol}
        enter_doc = {
            "timestamp": (base).astimezone(timezone.utc).isoformat(),
            "algo": algo,
            "contract": contract,
            "event": "enter",
            "action": side_u,
            "entry_action": side_u,
            "quantity": qty_sign,
            "price": float(entry),
            "pnl": None,
            "cci": float(cci),
            "emas": {f"EMA{k}": float(v) for k, v in emas.items()},
        }
        pnl = (exit_ - entry) * qty_sign
        exit_doc = {
            "timestamp": (base + timedelta(minutes=3)).astimezone(timezone.utc).isoformat(),
            "algo": algo,
            "contract": contract,
            "event": "exit",
            "action": exit_side,
            "entry_action": side_u,
            "exit_action": exit_side,
            "quantity": qty_sign,
            "price": float(exit_),
            "pnl": float(pnl),
            "cci": float(cci + 1.5),
            "emas": {f"EMA{k}": float(v) for k, v in emas.items()},
            "reason": reason,
        }
        docs.extend([enter_doc, exit_doc])

    # A few realistic pairs
    trade_pair(
        algo="CCI14_200_TradingAlgorithm",
        symbol="CL",
        side="BUY",
        entry=100.25,
        exit_=100.55,
        emas={10: 99.8, 20: 99.5, 32: 99.3, 50: 98.9, 100: 98.1, 200: 97.5},
        cci=112.4,
        reason="TP_fill",
    )
    trade_pair(
        algo="CCI14_200_TradingAlgorithm",
        symbol="CL",
        side="SELL",
        entry=101.10,
        exit_=102.00,  # loss for short
        emas={10: 100.7, 20: 100.4, 32: 100.1, 50: 99.8, 100: 99.2, 200: 98.6},
        cci=-128.9,
        reason="SL_fill",
    )
    trade_pair(
        algo="FibonacciTradingAlgorithm",
        symbol="CL",
        side="BUY",
        entry=98.70,
        exit_=98.40,
        emas={10: 98.5, 20: 98.4},
        cci=15.2,
        reason="manual",
    )
    return docs


def main() -> int:
    # Flags/args
    args = [a for a in sys.argv[1:] if a]
    preview = False
    if_empty = False
    force_seed = False
    index = "trades"
    # Simple flag parsing (order-insensitive)
    for a in list(args):
        if a == "--preview":
            preview = True
            args.remove(a)
        elif a == "--if-empty":
            if_empty = True
            args.remove(a)
        elif a == "--force":
            force_seed = True
            args.remove(a)
    if args:
        index = args[0]

    # Always build docs (for preview or indexing)
    docs = build_dummy_docs(datetime.now(timezone.utc))

    if preview:
        print(f"Previewing {len(docs)} dummy trade docs (no ES required):")
        for d in docs[:5]:
            pprint(d)
        if len(docs) > 5:
            print(f"... and {len(docs)-5} more")
        return 0

    es = get_es_client()
    if es is None:
        print("Elasticsearch client not installed or ES_URL unreachable.\n"
              "- Install client: pip install 'elasticsearch>=8'\n"
              "- Or run with --preview to just see the docs without indexing.")
        return 1

    try:
        wait_for_es(es)
    except Exception as e:  # pragma: no cover - environment dependent
        print(f"Could not reach Elasticsearch: {e}\n"
              "- Start Docker Desktop and run: docker compose up -d\n"
              "- Or set ES_URL to an accessible cluster and retry.\n"
              "- Or run with --preview to just print docs.")
        return 2

    # Ensure index exists
    ensure_index(es, index, mappings=TRADE_MAPPING)

    # Optionally skip seeding if index already has documents
    if if_empty and not force_seed:
        try:
            # count API returns {'count': N, ...}
            cnt = es.count(index=index).get('count', 0)
        except Exception:
            cnt = 0  # if count fails treat as empty to avoid noisy failures in dev
        if cnt > 0:
            print(f"Index '{index}' already has {cnt} docs — skipping seeding (use --force to reseed)")
            return 0
    bulk_index(es, index, docs)
    try:
        es.indices.refresh(index=index)
    except Exception:
        pass

    # Fetch a few docs to show how they look
    res = es.search(index=index, size=5, sort=[{"timestamp": {"order": "desc"}}])
    hits = res.get("hits", {}).get("hits", [])
    print(f"Indexed {len(docs)} docs into index '{index}'. Showing {len(hits)} recent docs:")
    for h in hits:
        src = h.get("_source", {})
        pprint(src)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
