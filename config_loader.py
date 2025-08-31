import json
from types import SimpleNamespace
from ib_insync import Future

def load_config(path):
    with open(path) as f:
        raw_cfg = json.load(f)

    cfg = SimpleNamespace(**raw_cfg)

    cfg.contract = Future(
        symbol=cfg.symbol,
        lastTradeDateOrContractMonth=cfg.expiry,
        exchange=cfg.exchange,
        currency=cfg.currency
    )

    return cfg