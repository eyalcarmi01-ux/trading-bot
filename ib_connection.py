from ib_insync import IB, Future, Stock

def connect_ib(host='127.0.0.1', port=7497, client_id=11):
    ib = IB()
    ib.connect(host, port, clientId=client_id)
    return ib

def get_contract(cfg):
    if cfg.type == 'future':
        return Future(
            symbol=cfg.symbol,
            lastTradeDateOrContractMonth=cfg.expiry,
            exchange=cfg.exchange,
            currency=cfg.currency
        )
    elif cfg.type == 'stock':
        return Stock(
            symbol=cfg.symbol,
            exchange=cfg.exchange,
            currency=cfg.currency
        )
    else:
        raise ValueError("Unsupported contract type")