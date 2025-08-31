from datetime import datetime
from logger_setup import logger
from ib_insync import MarketOrder, LimitOrder, StopOrder
import math

#open_positions = []

def contracts_match(c1, c2):
    return (
        c1.symbol == c2.symbol and
        c1.secType == c2.secType and
        c1.exchange == c2.exchange and
        c1.currency == c2.currency and
        c1.lastTradeDateOrContractMonth == c2.lastTradeDateOrContractMonth
    )

def order_filled(ib, order_id):
    for trade in ib.trades():
        if trade.order.orderId == order_id:
            return trade.orderStatus.status == 'Filled'
    return False


def get_market_price(tick):
    prices = [tick.last, tick.close, tick.bid, tick.ask]
    valid_prices = [p for p in prices if isinstance(p, (int, float)) and not math.isnan(p)]

    if valid_prices:
        return round(sum(valid_prices) / len(valid_prices), 2)

    logger.warning("⚠️ No valid market price found in tick data.")
    return None
    
from ib_insync import MarketOrder

from ib_insync import MarketOrder
from logger_setup import logger


from datetime import datetime

from datetime import datetime
from ib_insync import MarketOrder, LimitOrder, StopOrder
import math
from ib_insync import MarketOrder, LimitOrder, StopOrder
from datetime import datetime
import math

def reset_trade_state(cfg):
    cfg.trade_active = False
    cfg.active_direction = None
    cfg.active_stop_price = None
    cfg.active_sl_order_id = None
    cfg.active_tp_order_id = None

    logger.info("🔄 Trade state reset — bot is idle.")
    logger.info(f"📌 Trade active: {cfg.trade_active} | Direction: {cfg.active_direction}")

def place_bracket_orders(cfg, ib, quantity, action):
    # הגנה מפני פתיחת עסקה כפולה
    in_position = any(
        p.contract.conId == cfg.contract.conId and p.position != 0
        for p in ib.positions()
    )

    if cfg.trade_active or in_position:
        logger.warning("⛔ Trade already active or position open — skipping bracket order.")
        return

    tick = ib.reqMktData(cfg.contract, snapshot=True)
    ib.sleep(1)
    ref_price = tick.last or tick.close or tick.ask or tick.bid

    if not isinstance(ref_price, (int, float)):
        logger.warning("⚠️ No valid price — skipping order.")
        return

    tp_ticks = cfg.tp_ticks_long if action == 'BUY' else cfg.tp_ticks_short
    sl_ticks = cfg.sl_ticks

    tp = round(ref_price + cfg.tick_size * (tp_ticks if action == 'BUY' else -tp_ticks), 2)
    sl = round(ref_price + cfg.tick_size * (-sl_ticks if action == 'BUY' else sl_ticks), 2)

    cfg.trade_active = True
    cfg.active_direction = 'LONG' if action == 'BUY' else 'SHORT'
    cfg.active_stop_price = sl

    entry_order = MarketOrder(action, quantity)
    entry_order.transmit = False
    ib.placeOrder(cfg.contract, entry_order)

    sl_order = StopOrder('SELL' if action == 'BUY' else 'BUY', quantity, sl)
    sl_order.transmit = False
    sl_order.parentId = entry_order.orderId
    ib.placeOrder(cfg.contract, sl_order)

    tp_order = LimitOrder('SELL' if action == 'BUY' else 'BUY', quantity, tp)
    tp_order.transmit = True
    tp_order.parentId = entry_order.orderId
    ib.placeOrder(cfg.contract, tp_order)

    cfg.active_sl_order_id = sl_order.orderId
    cfg.active_tp_order_id = tp_order.orderId

    logger.info(f"✅ Bracket {action} order sent | Entry: {ref_price:.2f} | TP: {tp:.2f} | SL: {sl:.2f}")
    logger.info(f"📌 Trade active: {cfg.trade_active} | Direction: {cfg.active_direction}")

def monitor_stop_and_force_close(cfg):
    logger.info("🚦 Monitoring active positions...")

    timestamp_minute = datetime.now().replace(second=0, microsecond=0)
    current_price = cfg.market_prices.get(timestamp_minute)

    if current_price is None:
        tick = cfg.ib.reqMktData(cfg.contract, snapshot=True)
        cfg.ib.sleep(1)
        current_price = get_market_price(tick)

    if not isinstance(current_price, (int, float)):
        logger.warning("⚠️ Invalid market price — skipping monitoring.")
        return

    still_open = any(
        p.contract.conId == cfg.contract.conId and p.position != 0
        for p in cfg.ib.positions()
    )

    tp_filled = order_filled(cfg.ib, cfg.active_tp_order_id)
    sl_filled = order_filled(cfg.ib, cfg.active_sl_order_id)

    if tp_filled or sl_filled:
        reason = "take profit" if tp_filled else "stop loss"
        logger.warning(f"⚠️ {reason.capitalize()} filled — closing position @ {current_price:.2f}")

        for order in cfg.ib.orders():
            try:
                cfg.ib.cancelOrder(order)
            except Exception as e:
                logger.warning(f"⚠️ Failed to cancel order {order.orderId}: {e}")

        reset_trade_state(cfg)
        return

    if still_open and cfg.active_stop_price is not None:
        if (
            cfg.active_direction == 'LONG' and current_price <= cfg.active_stop_price or
            cfg.active_direction == 'SHORT' and current_price >= cfg.active_stop_price
        ):
            logger.warning(f"❌ Price crossed stop level — forcing close @ {current_price:.2f}")
            action = 'SELL' if cfg.active_direction == 'LONG' else 'BUY'
            close_order = MarketOrder(action, cfg.quantity)
            cfg.ib.placeOrder(cfg.contract, close_order)

            for order in cfg.ib.orders():
                try:
                    cfg.ib.cancelOrder(order)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to cancel order {order.orderId}: {e}")

            reset_trade_state(cfg)