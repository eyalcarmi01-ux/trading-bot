import math
from ib_insync import IB
from logger_setup import logger  # שימוש ב־logger אחיד מההגדרה המרכזית


# 📈 חישוב סדרת EMA מלאה
def calculate_ema_series(series, span=10):
    if not series or len(series) < span:
        logger.warning(f"⚠️ Not enough data to calculate EMA series ({span})")
        return []

    ema_series = []
    alpha = 2 / (span + 1)
    ema = sum(series[:span]) / span  # התחלה עם ממוצע פשוט

    ema_series.append(round(ema, 2))
    for price in series[span:]:
        ema = (price * alpha) + (ema * (1 - alpha))
        ema_series.append(round(ema, 2))

    return ema_series

# 🧠 חישוב ערכי EMA אחרונים עבור כמה תקופות
def get_latest_emas(close_series, spans=(10, 100, 200)):
    if not close_series or not isinstance(close_series, list):
        logger.warning("⚠️ close_series is invalid — returning empty EMA dict")
        return {}

    ema_values = {}
    for span in spans:
        if len(close_series) >= span:
            ema_series = calculate_ema_series(close_series, span=span)
            ema_values[span] = ema_series[-1] if ema_series else None
        else:
            logger.warning(f"⚠️ Not enough data for EMA({span})")
            ema_values[span] = None

    return ema_values

def get_latest_tp(tick):
    high = tick.high
    low = tick.low
    close = tick.close or tick.last or tick.ask or tick.bid

    if not all(isinstance(x, (int, float)) and not math.isnan(x) for x in [high, low, close]):
        logger.warning("⚠️ Invalid tick data — skipping TP calculation")
        return None

    tp = (high + low + close) / 3
    logger.info(f"📊 TP calculated: {tp:.2f}")
    return round(tp, 2)

def fetch_initial_data(ib, contract):
    bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr='12000 S',
        barSizeSetting='1 min',
        whatToShow='TRADES',
        useRTH=False,
        formatDate=1
    )

    ib.sleep(2)

    if not bars:
        logger.warning("⚠️ No historical data received.")
        return []

    tp_series = []
    for i, bar in enumerate(bars):
        try:
            values = [bar.high, bar.low, bar.close]
            if all(isinstance(v, (int, float)) and not math.isnan(v) and not math.isinf(v) for v in values):
                tp = sum(values) / 3
                tp_series.append(round(tp, 2))
            else:
                logger.warning(f"⚠️ Invalid bar at index {i}: {values}")
        except Exception as e:
            logger.error(f"⛔ Error processing bar at index {i}: {e}")

    logger.info(f"📊 Fetched {len(tp_series)} valid TP values from historical data")
    return tp_series

def get_latest_tick(ib, contract):
    ticker = ib.reqMktData(contract, "", False, False)
    ib.sleep(0.5)
    return ticker

def run_tp_stream(price_series, current_price):
    if not isinstance(current_price, (int, float)) or math.isnan(current_price) or math.isinf(current_price):
        logger.warning(f"⚠️ Invalid price: {current_price}")
        return None

    tp = round(current_price, 2)

    logger.info(f"💰 Market Price: {tp:.2f}")

    if not price_series or tp != price_series[-1]:
        price_series.append(tp)
        if len(price_series) > 300:
            price_series.pop(0)
        logger.info(f"📥 New TP added: {tp}")
    else:
        logger.info(f"🔁 TP unchanged: {tp}")

    recent_tp = [f"{val:.2f}" for val in price_series[-10:]]
    logger.info(f"🧪 Recent TP Values: {', '.join(recent_tp)}")

    return tp

def fetch_close_series(ib, contract, bars_count=200):
    bars = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr=f'{bars_count * 60} S',  # 200 דקות
        barSizeSetting='1 min',
        whatToShow='TRADES',
        useRTH=False,
        formatDate=1
    )

    ib.sleep(2)

    close_series = []
    for bar in bars:
        if isinstance(bar.close, (int, float)) and not math.isnan(bar.close):
            close_series.append(bar.close)

    return close_series