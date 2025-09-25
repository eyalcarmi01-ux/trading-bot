#!/usr/bin/env python3
"""
Fix incorrect exit actions in Elasticsearch trade documents.

Context: Some historical docs logged 'action' for exit events equal to the entry side.
This script updates those docs so that for event=='exit':
  - if entry_action=='BUY' and action=='BUY'  -> set action=exit_action='SELL'
  - if entry_action=='SELL' and action=='SELL'-> set action=exit_action='BUY'

Usage:
  python3 scripts/fix_exit_actions_es.py --index trades --apply
  # dry-run (default):
  python3 scripts/fix_exit_actions_es.py --index trades

Environment variables:
  ES_URL              (default http://localhost:9200)
  ES_USERNAME/ES_PASSWORD for basic auth if needed
  TRADES_ES_INDEX     default index name if --index not provided
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    from elasticsearch import Elasticsearch
except Exception:
    Elasticsearch = None  # type: ignore


def get_client() -> "Elasticsearch | None":
    if Elasticsearch is None:
        return None
    url = os.getenv("ES_URL", "http://localhost:9200")
    user = os.getenv("ES_USERNAME")
    pwd = os.getenv("ES_PASSWORD")
    if user and pwd:
        return Elasticsearch(url, basic_auth=(user, pwd))
    return Elasticsearch(url)


def update_by_query(es: "Elasticsearch", index: str, entry: str, wrong_action: str, correct_action: str, dry_run: bool) -> dict:
    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"event": "exit"}},
                    {"term": {"entry_action": entry}},
                    {"term": {"action": wrong_action}},
                ]
            }
        },
    }
    if dry_run:
        # Count matching docs
        res = es.count(index=index, body=query["query"])  # type: ignore[arg-type]
        return {"matched": res.get("count", 0), "updated": 0}
    # Apply painless script to set fields
    body = {
        **query,
        "script": {
            "lang": "painless",
            "source": (
                f"ctx._source.action='{correct_action}'; ctx._source.exit_action='{correct_action}';"
            ),
        },
        # Ensure we refresh so subsequent reads see updates
        "refresh": True,
    }
    res = es.update_by_query(index=index, body=body, conflicts="proceed", refresh=True, wait_for_completion=True)  # type: ignore[arg-type]
    return {"matched": res.get("total", 0), "updated": res.get("updated", 0)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Fix incorrect exit actions in ES trade docs")
    ap.add_argument("--index", default=os.getenv("TRADES_ES_INDEX", "trades"), help="Elasticsearch index or alias to update (default: trades)")
    ap.add_argument("--apply", action="store_true", help="Apply updates; otherwise dry-run counts only")
    args = ap.parse_args(argv)

    es = get_client()
    if es is None:
        print("error: elasticsearch client isn't installed. pip install elasticsearch>=8")
        return 2

    index = args.index
    dry = not args.apply
    mode = "DRY-RUN" if dry else "APPLY"
    print(f"[fix-exit-actions] Mode={mode} Index={index}")

    # Case 1: entry BUY, wrong exit action BUY -> should be SELL
    r1 = update_by_query(es, index, entry="BUY", wrong_action="BUY", correct_action="SELL", dry_run=dry)
    # Case 2: entry SELL, wrong exit action SELL -> should be BUY
    r2 = update_by_query(es, index, entry="SELL", wrong_action="SELL", correct_action="BUY", dry_run=dry)

    print(f"[fix-exit-actions] BUY->SELL fix: matched={r1['matched']} updated={r1['updated']}")
    print(f"[fix-exit-actions] SELL->BUY fix: matched={r2['matched']} updated={r2['updated']}")
    total_upd = r1.get("updated", 0) + r2.get("updated", 0)
    print(f"[fix-exit-actions] Done. total_updated={total_upd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
