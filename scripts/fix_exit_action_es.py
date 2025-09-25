"""
fix_exit_action_es.py

Corrects historical trade records in Elasticsearch where the exit action is not the opposite of the entry action.

Usage:
    python3 scripts/fix_exit_action_es.py [--index trades]

Requires: elasticsearch>=8, ES_URL env var (default: http://localhost:9200)
"""
import os
import sys
from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan, bulk

def get_es_client():
    url = os.getenv("ES_URL", "http://localhost:9200")
    return Elasticsearch(url)

def fix_exit_actions(es, index):
    # Find all exit events
    q = {
        "query": {"term": {"event": "exit"}}
    }
    actions = []
    for doc in scan(es, index=index, query=q):
        src = doc["_source"]
        entry = src.get("entry_action")
        exit_action = src.get("exit_action")
        action = src.get("action")
        if not entry or not action:
            continue
        entry = entry.upper()
        correct_exit = "SELL" if entry == "BUY" else ("BUY" if entry == "SELL" else None)
        if not correct_exit:
            continue
        # If either exit_action or action is wrong, fix
        needs_update = (exit_action != correct_exit) or (action != correct_exit)
        if needs_update:
            doc_id = doc["_id"]
            actions.append({
                "_op_type": "update",
                "_index": index,
                "_id": doc_id,
                "doc": {
                    "exit_action": correct_exit,
                    "action": correct_exit
                }
            })
    if actions:
        print(f"Updating {len(actions)} exit records...")
        bulk(es, actions)
        print("Done.")
    else:
        print("No corrections needed.")

def main():
    index = sys.argv[1] if len(sys.argv) > 1 else os.getenv("TRADES_ES_INDEX", "trades")
    es = get_es_client()
    fix_exit_actions(es, index)

if __name__ == "__main__":
    main()
