from datetime import datetime
from zoneinfo import ZoneInfo  # אם אתה על Python 3.9+

from datetime import datetime, time
from zoneinfo import ZoneInfo  # אם אתה על Python 3.9+

def should_trade_now(cfg):
    now = datetime.now(ZoneInfo("Asia/Jerusalem")).time()
    start = time(hour=cfg.trade_start["hour"], minute=cfg.trade_start["minute"])
    end = time(hour=cfg.trade_end["hour"], minute=cfg.trade_end["minute"])
    return start <= now <= end

def check_trade_conditions(cci):
    if cci > 200:
        return 'SELL'
    elif cci < -200:
        return 'BUY'
    else:
        return None
