import time
import csv
import math
import json
from datetime import datetime, timedelta
from order_manager import (
    place_bracket_orders,
    monitor_stop_and_force_close,
    reset_trade_state  
)
from indicators import (
    calculate_cci,
    get_latest_emas,
    calculate_ema,
    clean_prices_with_previous,
    log_ema_snapshot
)
from data_fetcher import run_tp_stream, get_latest_tick
from logger_setup import logger
from ib_insync import Future

# טעינת קובץ קונפיג
with open('config.json') as f:
    config_data = json.load(f)

class Config:
    pass

cfg = Config()
for key, value in config_data.items():
    setattr(cfg, key, value)

# טעינת פרמטרים חדשים מהקונפיג
cfg.tick_size = getattr(cfg, 'tick_size', 0.01)
cfg.tp_ticks_long = getattr(cfg, 'tp_ticks_long', 28)
cfg.tp_ticks_short = getattr(cfg, 'tp_ticks_short', 35)
cfg.sl_ticks = getattr(cfg, 'sl_ticks', 17)

# הגדרת חוזה
cfg.contract = Future(
    symbol=cfg.symbol,
    lastTradeDateOrContractMonth=cfg.expiry,
    exchange=cfg.exchange,
    currency=cfg.currency
)

# אתחול מצב פנימי
cfg.entry_price = None
cfg.stop_price = None
cfg.take_profit = None
cfg.trade_active = False
cfg.active_direction = None
cfg.active_stop_price = None
cfg.active_tp_order_id = None
cfg.active_sl_order_id = None
cfg.market_prices = {}

def update_close_series(tick, close_series, max_length=500):
    price = get_market_price(tick)
    if not isinstance(price, (int, float)) or math.isnan(price) or math.isinf(price):
        logger.warning("⚠️ Invalid price — not added to close_series.")
        return

    close_series.append(price)
    if len(close_series) > max_length:
        close_series.pop(0)

    logger.info(f"📊 Updated close_series with price: {price:.2f} | Length: {len(close_series)}")

def get_market_price(tick):
    price = tick.last
    if isinstance(price, (int, float)) and not math.isnan(price):
        return round(price, 2)
    logger.warning("⚠️ No valid LAST price found in tick data.")
    return None

def run_loop(cfg, strategy_module, price_series, close_series, ib, contract):
    logger.info("🧼 Initial state — no active position.")

    try:
        now = datetime.now()
        start_time = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        wait_seconds = (start_time - now).total_seconds()
        logger.info(f"⏳ Waiting {int(wait_seconds)} seconds for round-minute start...")
        time.sleep(wait_seconds)

        while True:
            time.sleep(1)
            timestamp_minute = datetime.now().replace(second=0, microsecond=0)
            tick = get_latest_tick(ib, contract)

            market_price = get_market_price(tick)
            if market_price is None:
                logger.warning("⚠️ No valid market price — skipping cycle.")
                continue

            cfg.market_prices[timestamp_minute] = market_price
            logger.info(f"📈 Market price saved for {timestamp_minute}: {market_price:.2f}")

            update_close_series(tick, close_series)

            current_price = close_series[-1] if close_series else None
            if current_price is None:
                logger.warning("⚠️ No price data available — skipping cycle.")
                continue

            tp = run_tp_stream(price_series, current_price)
            if tp is None:
                logger.warning("⚠️ TP not calculated — skipping this cycle.")
                continue

            cleaned_series = clean_prices_with_previous(close_series)
            spans = [10, 20, 32, 50, 100, 200]
            live_emas = {
                span: calculate_ema(cleaned_series, span) if len(cleaned_series) >= span else None
                for span in spans
            }

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ema_log = " | ".join([
                f"EMA({s})={live_emas[s]:.2f}" if live_emas[s] else f"EMA({s})=N/A"
                for s in spans
            ])
            logger.info(f"🕒 {timestamp} | Live EMAs: {ema_log}")

            cci, avg_tp, dev, arrow = calculate_cci(price_series)
            logger.info(f"📊 CCI: {cci:.2f} | Mean TP: {avg_tp:.2f} | Dev: {dev:.2f} | Arrow: {arrow}")

            # בדיקה כפולה: גם לפי IB וגם לפי מצב פנימי
            in_position = any(
                p.contract.conId == contract.conId and p.position != 0
                for p in ib.positions()
            )

            if cfg.trade_active or in_position:
                logger.info("⏸️ Trade already active — skipping new trades.")
                monitor_stop_and_force_close(cfg)
                time.sleep(cfg.interval)
                continue

            logger.info("🚦 Checking trade conditions...")

            if hasattr(strategy_module, 'should_trade_now') and strategy_module.should_trade_now(cfg):
                action = strategy_module.check_trade_conditions(cci)
                if action:
                    logger.info(f"✅ Signal detected: {action}. Sending order...")
                    place_bracket_orders(cfg, ib, quantity=cfg.quantity, action=action)
                else:
                    logger.info("🔍 No trade signal at the moment.")
            else:
                logger.info("⏸️ Trading window closed — no new trades.")

            time.sleep(cfg.interval)

    except KeyboardInterrupt:
        logger.info("🛑 Loop interrupted by user.")
    logger.info("🛑 Stopped by user.")