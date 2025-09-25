import os
from typing import Any, Dict, Optional

try:
    from elasticsearch import Elasticsearch, helpers
except Exception:  # pragma: no cover - optional dependency
    Elasticsearch = None  # type: ignore
    helpers = None  # type: ignore


def get_es_client(url: Optional[str] = None) -> Optional["Elasticsearch"]:
    """Return an Elasticsearch client or None if dependency missing.

    Security is disabled in docker-compose by default; if you enable it,
    set ES_USERNAME and ES_PASSWORD in the environment and pass basic_auth.
    """
    url = url or os.getenv("ES_URL", "http://localhost:9200")
    if Elasticsearch is None:
        return None
    user = os.getenv("ES_USERNAME")
    pwd = os.getenv("ES_PASSWORD")
    if user and pwd:
        return Elasticsearch(url, basic_auth=(user, pwd))
    return Elasticsearch(url)


def ensure_index(es: "Elasticsearch", index: str, mappings: Optional[Dict[str, Any]] = None) -> None:
    if not es.indices.exists(index=index):
        body = {"mappings": mappings or {"properties": {"timestamp": {"type": "date"}}}}
        es.indices.create(index=index, mappings=body.get("mappings"))


def index_doc(es: "Elasticsearch", index: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    return es.index(index=index, document=doc)


def bulk_index(es: "Elasticsearch", index: str, docs: list[Dict[str, Any]]) -> None:
    actions = ({"_index": index, "_source": d} for d in docs)
    helpers.bulk(es, actions)
