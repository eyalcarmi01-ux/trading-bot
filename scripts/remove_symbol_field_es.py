#!/usr/bin/env python3
"""
Remove the top-level 'symbol' field from all documents in the trades and trades_seed
indices so Discover rows no longer show it. This keeps contract.symbol intact.

Usage:
    - In-place cleanup: python3 scripts/remove_symbol_field_es.py
    - Reindex + alias swap: python3 scripts/remove_symbol_field_es.py --reindex
"""
import argparse
import os
import sys
import time

# Ensure project root is on sys.path so we can import es_client
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import es_client as _es
except Exception as e:
    print(f"Failed to import es_client: {e}")
    sys.exit(1)


def remove_field(index: str, field: str = "symbol") -> None:
    client = _es.get_es_client()
    if client is None:
        print("Elasticsearch client unavailable. Ensure ES is running and ES_URL is set if needed.")
        sys.exit(2)
    if not client.indices.exists(index=index):
        print(f"Index '{index}' does not exist; skipping.")
        return

    script = {
        "source": "if (ctx._source.containsKey(params.f)) { ctx._source.remove(params.f); }",
        "lang": "painless",
        "params": {"f": field},
    }
    body = {
        "script": script,
        "query": {"exists": {"field": field}},
    }
    print(f"Updating index '{index}': removing field '{field}' from matching documents…")
    resp = client.update_by_query(
        index=index,
        body=body,
        conflicts="proceed",
        refresh=True,
        slices="auto",
        wait_for_completion=True,
        request_timeout=600,
    )
    updated = resp.get("updated", 0)
    total = resp.get("total", 0)
    print(f"Removed '{field}' from {updated}/{total} docs in '{index}'.")


def reindex_without_field(index: str, field: str = "symbol") -> None:
    client = _es.get_es_client()
    if client is None:
        print("Elasticsearch client unavailable. Ensure ES is running and ES_URL is set if needed.")
        sys.exit(2)
    if not client.indices.exists(index=index):
        print(f"Index '{index}' does not exist; skipping.")
        return

    # Build destination index name and retrieve source mapping
    suffix = time.strftime("%Y%m%d%H%M%S")
    dest = f"{index}_clean_{suffix}"
    src_mapping = client.indices.get_mapping(index=index)
    props = (
        src_mapping.get(index, {})
        .get("mappings", {})
        .get("properties", {})
        .copy()
    )
    if field in props:
        props.pop(field, None)
    mappings = {"properties": props}

    print(f"Creating destination index '{dest}' without '{field}' property…")
    client.indices.create(index=dest, mappings=mappings)

    script = {
        "source": "if (ctx._source.containsKey(params.f)) { ctx._source.remove(params.f); }",
        "lang": "painless",
        "params": {"f": field},
    }
    body = {"source": {"index": index}, "dest": {"index": dest}, "script": script}
    print(f"Reindexing from '{index}' to '{dest}' while stripping '{field}'…")
    resp = client.reindex(body=body, refresh=True, wait_for_completion=True, request_timeout=1800)
    created = resp.get("created", 0)
    total = resp.get("total", 0)
    print(f"Reindexed {created}/{total} docs to '{dest}'.")

    # Remove original index so we can create an alias with the same name
    print(f"Deleting original index '{index}'…")
    client.indices.delete(index=index)

    # Create an alias with the original name pointing to dest
    print(f"Creating alias '{index}' -> '{dest}' (write index)…")
    client.indices.put_alias(index=dest, name=index, is_write_index=True)
    print(f"Alias swap complete. '{index}' now points to '{dest}'.")


def main():
    parser = argparse.ArgumentParser(description="Remove 'symbol' field from ES indices.")
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Reindex into a fresh index without the field and alias-swap the original name.",
    )
    args = parser.parse_args()

    trades_index = os.getenv("TRADES_ES_INDEX", "trades")
    seed_index = os.getenv("TRADES_ES_SEED_INDEX", "trades_seed")
    for idx in (trades_index, seed_index):
        if args.reindex:
            reindex_without_field(idx, "symbol")
        else:
            remove_field(idx, "symbol")
    print("Done.")


if __name__ == "__main__":
    main()
