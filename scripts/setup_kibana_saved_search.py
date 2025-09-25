#!/usr/bin/env python3
"""Create Kibana Data Views for the 'trades' and 'trades_seed' indices and
import the saved Discover searches with the requested column order.

Usage:
  python scripts/setup_kibana_saved_search.py [--kibana-url http://localhost:5601] \
    [--file .kibana_saved_search_trades.json] \
    [--seed-file .kibana_saved_search_seed.json]

Notes:
  - Assumes Kibana is running locally with security disabled (as in docker-compose.yml).
  - If Kibana has security enabled, set ES_USERNAME/ES_PASSWORD and basic auth headers.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def kibana_request(method: str, url: str, path: str, payload: dict | list | None = None) -> tuple[int, dict | list | str | None]:
    full = url.rstrip('/') + path
    data = None
    headers = {"kbn-xsrf": "true", "Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(full, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            if not body:
                return resp.getcode(), None
            try:
                return resp.getcode(), json.loads(body)
            except json.JSONDecodeError:
                return resp.getcode(), body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = None
        return e.getcode(), (json.loads(body) if body else None)
    except urllib.error.URLError as e:
        raise SystemExit(f"Failed to reach Kibana at {full}: {e}")


def ensure_data_view(kibana_url: str, data_view_id: str, title: str, time_field: str) -> None:
    # Try to get existing saved object
    code, _ = kibana_request("GET", kibana_url, f"/api/saved_objects/index-pattern/{data_view_id}")
    if code == 200:
        print(f"Kibana Data View '{data_view_id}' already exists")
        return
    # Create new data view saved object
    payload = {"attributes": {"title": title, "timeFieldName": time_field}}
    code, body = kibana_request("POST", kibana_url, f"/api/saved_objects/index-pattern/{data_view_id}", payload)
    if code not in (200, 201):
        raise SystemExit(f"Failed to create Data View '{data_view_id}': {body}")
    print(f"Created Kibana Data View '{data_view_id}' for '{title}' with time field '{time_field}'")


def import_saved_search(kibana_url: str, saved_objects_file: str) -> None:
    with open(saved_objects_file, "r", encoding="utf-8") as f:
        objs = json.load(f)
    # Kibana bulk_create expects an array in the request body; pass overwrite as a query param
    code, body = kibana_request("POST", kibana_url, "/api/saved_objects/_bulk_create?overwrite=true", objs)
    if code not in (200, 201):
        raise SystemExit(f"Failed to import saved search: {body}")
    titles = [o.get("attributes", {}).get("title") for o in objs if o.get("type") == "search"]
    print(f"Imported/updated saved search(es): {', '.join(filter(None, titles))}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kibana-url", default=os.getenv("KIBANA_URL", "http://localhost:5601"))
    root = os.path.dirname(os.path.dirname(__file__))
    parser.add_argument("--file", default=os.path.join(root, 
                                                       ".kibana_saved_search_trades.json"))
    parser.add_argument("--seed-file", default=os.path.join(root,
                                                            ".kibana_saved_search_seed.json"))
    args = parser.parse_args(argv)

    # Ensure Data Views exist
    ensure_data_view(args.kibana_url, data_view_id="trades", title="trades", time_field="timestamp")
    ensure_data_view(args.kibana_url, data_view_id="trades_seed", title="trades_seed", time_field="timestamp")
    # Import saved Discover searches with ordered columns
    import_saved_search(args.kibana_url, args.file)
    if os.path.exists(args.seed_file):
        import_saved_search(args.kibana_url, args.seed_file)
    print("Kibana configured. Open Discover and select 'Trades Discover (Ordered)' and 'Seed/Priming Discover (Ordered)'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
