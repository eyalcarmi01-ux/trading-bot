import math
import time
import datetime
from logger_setup import logger  # שימוש נכון ב־logger אחיד

# 🧼 ניקוי סדרת מחירים
def clean_prices_with_previous(prices):
    if not prices or not isinstance(prices, list):
        logger.warning("⚠️ Price series is None, empty, or invalid — returning empty list")
        return []

    cleaned = []
    for i, p in enumerate(prices):
        if isinstance(p, (int, float)) and not math.isnan(p) and not math.isinf(p):
            cleaned.append(p)
        else:
            fallback = cleaned[-1] if cleaned else 0.0
            logger.warning(f"⚠️ Invalid price at index {i} — using fallback: {fallback}")
            cleaned.append(fallback)

    logger.info(f"🧼 Cleaned price series length: {len(cleaned)}")
    return cleaned

# 📈 חישוב EMA בודד
def calculate_ema(series, span=10):
    if not series or len(series) < span:
        logger.warning(f"⚠️ Not enough data to calculate EMA({span})")
        return None

    alpha = 2 / (span + 1)
    ema = series[0]
    for price in series[1:]:
        ema = (price * alpha) + (ema * (1 - alpha))
    return round(ema, 2)

# 📊 חישוב סדרת EMA מלאה
def calculate_ema_series(series, span=10):
    if not series or len(series) < span:
        logger.warning(f"⚠️ Not enough data to calculate EMA series ({span})")
        return []

    ema_series = []
    alpha = 2 / (span + 1)
    ema = series[0]
    for price in series:
        ema = (price * alpha) + (ema * (1 - alpha))
        ema_series.append(round(ema, 2))
    return ema_series

# 🧠 חישוב ערכי EMA אחרונים עבור כמה תקופות
def get_latest_emas(close_series: list, spans=(10, 100, 200)):
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

# 📐 חישוב CCI
def calculate_cci(tp_series: list, period: int = 14):
    tp_series = [tp for tp in tp_series if isinstance(tp, (int, float)) and not math.isnan(tp) and not math.isinf(tp)]
    logger.info(f"🧪 TP Series Length After Cleaning: {len(tp_series)}")

    if len(tp_series) < period:
        logger.warning("⚠️ Not enough data to calculate CCI.")
        return float('nan'), float('nan'), float('nan'), '⏸️'

    recent_tp = tp_series[-period:]
    sma_tp = sum(recent_tp) / period
    mean_dev = sum(abs(tp - sma_tp) for tp in recent_tp) / period

    if mean_dev == 0:
        logger.warning("⚠️ Mean deviation is zero — returning neutral CCI.")
        return 0.0, round(sma_tp, 2), 0.0, '⏸️'

    cci = (recent_tp[-1] - sma_tp) / (0.015 * mean_dev)
    arrow = '🔼' if cci > 100 else '🔽' if cci < -100 else '⏸️'

    #logger.info(f"📊 SMA (Average TP): {sma_tp:.4f}")
    #logger.info(f"📊 Mean Deviation: {mean_dev:.4f}")
    #logger.info(f"📈 CCI Calculated: {cci:.2f}")
    #logger.info(f"🧭 Trend Arrow: {arrow}")

    return round(cci, 2), round(sma_tp, 2), round(mean_dev, 4), arrow

# 🖼️ הדפסת תמונת מצב של EMA
def log_ema_snapshot(close_series):
    cleaned = clean_prices_with_previous(close_series)
    spans = [10, 20, 32, 50, 100, 200]

    latest_emas = []
    for span in spans:
        if len(cleaned) >= span:
            ema_series = calculate_ema_series(cleaned, span=span)
            latest_emas.append(f"EMA({span})={ema_series[-1]:.2f}")
        else:
            latest_emas.append(f"EMA({span})=N/A")
    logger.info("📊 EMA Snapshot: " + " | ".join(latest_emas))

    for span in spans:
        if len(cleaned) >= span:
            ema_series = calculate_ema_series(cleaned, span=span)
            last_10 = ema_series[-10:]
            formatted = ", ".join([f"{val:.2f}" for val in last_10])
            logger.info(f"📈 EMA({span}) last 10: {formatted}")
        else:
            logger.info(f"📈 EMA({span}) last 10: N/A")