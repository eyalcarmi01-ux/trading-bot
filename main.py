from config_loader import load_config
from ib_connection import connect_ib, get_contract
from data_fetcher import fetch_initial_data, fetch_close_series
from indicators import clean_prices_with_previous, get_latest_emas
from main_loop import run_loop
from logger_setup import logger
import importlib
import pandas as pd
from datetime import datetime

# טעינת קונפיג
CONFIG_PATH = 'config.json'
cfg = load_config(CONFIG_PATH)
cfg.market_prices = {}  # ✅ מוסיף את השדה החסר

# טעינת פרמטרים חדשים מהקונפיג
cfg.tick_size = cfg.tick_size if hasattr(cfg, 'tick_size') else 0.01
cfg.tp_ticks_long = cfg.tp_ticks_long if hasattr(cfg, 'tp_ticks_long') else 28
cfg.tp_ticks_short = cfg.tp_ticks_short if hasattr(cfg, 'tp_ticks_short') else 35
cfg.sl_ticks = cfg.sl_ticks if hasattr(cfg, 'sl_ticks') else 17

# אתחול משתני מצב פנימי
cfg.trade_active = False
cfg.active_direction = None
cfg.active_stop_price = None
cfg.active_tp_order_id = None
cfg.active_sl_order_id = None

# יצירת force_close_time מתוך הקונפיג החדש
now = datetime.now()
cfg.force_close_time = now.replace(
    hour=cfg.force_close["hour"],
    minute=cfg.force_close["minute"],
    second=0,
    microsecond=0
)
if cfg.force_close_time < now:
    cfg.force_close_time = cfg.force_close_time.replace(day=now.day + 1)

# ודא שהשדה open_positions קיים (למקרה של שימוש עתידי)
if not hasattr(cfg, 'open_positions'):
    cfg.open_positions = []

# התחברות ל־IB
ib = connect_ib()
cfg.ib = ib  # מוסיפים את ib לתוך cfg כדי להעביר אותו בין מודולים

# יצירת חוזה
cfg.contract = get_contract(cfg)
ib.qualifyContracts(cfg.contract)

# טעינת מודול אסטרטגיה
strategy_module = importlib.import_module(cfg.strategy_module)

# משיכת נתונים היסטוריים
price_series = fetch_initial_data(ib, cfg.contract)
price_series = clean_prices_with_previous(price_series)

# חישוב ממוצעים נעים חיים
close_series = fetch_close_series(ib, cfg.contract, bars_count=200)
ema_values = get_latest_emas(close_series, spans=(10, 100, 200))
logger.info(f"📊 EMA Historical Values — 10: {ema_values[10]}, 100: {ema_values[100]}, 200: {ema_values[200]}")

# הרצת הלולאה הראשית
run_loop(cfg, strategy_module, price_series, close_series, ib, cfg.contract)

# הרצת סימולציה (אם תרצה להפעיל)
# df = run_simulation(cfg, num_trades=10)
# df.to_excel("simulation_results.xlsx", index=False)
# print("📊 סימולציה הסתיימה ונשמרה לקובץ Excel.")