#fibonacci_CL_v1.1.py 28.08.25
from ib_insync import *
import datetime, time, sys, math
from statistics import stdev, mean

# === הגדרות כלליות ===
EMA_FAST_PERIOD = 10
EMA_SLOW_PERIOD = 200
CCI_PERIOD = 14
K_FAST = 2 / (EMA_FAST_PERIOD + 1)
K_SLOW = 2 / (EMA_SLOW_PERIOD + 1)
TICK_SIZE = 0.01
SL_TICKS = 7 #17
TP_TICKS_LONG = 10 #  28
TP_TICKS_SHORT = 10 # 35
QUANTITY = 1

# === משתנים גלובליים ===
price_history = []
cci_values = []
prev_cci = None
ema_fast = ema_slow = None
paused_notice_shown = False
trade_active = False
active_stop_price = None
active_direction = None
active_sl_order_id = None
active_tp_order_id = None
MANUAL_MA_120 = 62.37  #מוזן ידנית#
last_stop_direction = None  # יכול להיות 'LONG' או 'SHORT'
active_tp_price = None  # נשמר בזמן שליחת העסקה
active_stop_price = None
active_direction = None
trade_active = False
contract = Future(symbol='CL', lastTradeDateOrContractMonth='202602', exchange='NYMEX', currency='USD')


# === קלט מהשורת הרצה ===
if len(sys.argv) >= 4:
    cli_price = float(sys.argv[1])
    CHECK_INTERVAL = int(sys.argv[2])
    initial_ema = float(sys.argv[3])
else:
    cli_price = 65.00
    CHECK_INTERVAL = 60
    initial_ema = 64.80
    print("⚠️ Using default values")

ema_slow = initial_ema
ema_fast = None  # נחשב אותו מאוחר יותר מתוך price_history

# === התחברות ל־IB ===
ib = IB()
contract = Future(symbol='CL', lastTradeDateOrContractMonth='202602', exchange='NYMEX', currency='USD')
#contract = Future(symbol='CL', lastTradeDateOrContractMonth='202511', exchange='NYMEX', currency='USD')
#contract = Future(symbol='CL', lastTradeDateOrContractMonth='202510', exchange='NYMEX', currency='USD')
ib.connect('127.0.0.1', 7497, clientId=99)
ib.qualifyContracts(contract)
print("✅ Connected to IB Gateway\n")

# === TEST ORDER לבדוק תקשורת ===
test_price = round(cli_price / 2, 2)
print(f"🧪 TEST order sent @ {test_price}")
test_order = LimitOrder('BUY', 1, test_price)
ib.placeOrder(contract, test_order)
ib.sleep(5)
ib.cancelOrder(test_order)
print("✅ TEST ORDER SENT AND CANCELLED SUCCESSFULLY\n")

# === חכה לתחילת דקה עגולה ===
now = datetime.datetime.now()
wait_sec = 60 - now.second
print(f"⏳ Waiting {wait_sec} seconds for round-minute start...")
time.sleep(wait_sec)
print(f"🚀 Starting at {datetime.datetime.now().strftime('%H:%M:%S')}\n")

# === איסוף מחירים ראשוני לחישוב CCI14 ===
#print("🔍 Preparing CCI14 calculation: collecting price history...\n")
#while len(price_history) < CCI_PERIOD:
#    tick = ib.reqMktData(contract, snapshot=True)
#    ib.sleep(CHECK_INTERVAL)
#    price = tick.last or tick.close or tick.ask or tick.bid
#    if isinstance(price, (int, float)):
#        price_history.append(price)
#        print(f"⏳ CCI History: {len(price_history)}/{CCI_PERIOD} collected")
#    else:
#        print("⚠️ Invalid price — skipping")

#print("✅ CCI14 history complete — bot ready to start\n")

# === אתחול EMA200 מתוך ערך קבוע ===
ema_slow = initial_ema

# === חישוב EMA10 מתוך 10 המחירים האחרונים ===
#recent_prices = price_history[-EMA_FAST_PERIOD:]
#ema_fast = recent_prices[0]  # התחלה

#for price in recent_prices[1:]:
#    ema_fast = round(price * K_FAST + ema_fast * (1 - K_FAST), 4)
#print(f"📊 EMA10 source prices: {recent_prices}")

#print(f"📈 Initial EMA10 calculated from history: {ema_fast}")

# === צבעים למסך (ANSI Terminal Codes) ===
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# === פונקציות עזר מחזירה ערך prev_cci===
#def calculate_and_log_cci(prices, time_str):
#    global prev_cci
#    if len(prices) < CCI_PERIOD:
#        print(f"{time_str} ⚠️ Not enough data for CCI")
#        return None

#    typical_prices = prices[-CCI_PERIOD:]
#    avg_tp = mean(typical_prices)
#    dev = stdev(typical_prices)

#    if dev == 0:
#        print(f"{time_str} ⚠️ StdDev is zero — CCI = 0")
#        return 0
#
#    cci = (typical_prices[-1] - avg_tp) / (0.015 * dev)
#
#    if cci >= 120:
#        cci_display = f"{RED}{round(cci, 2)}{RESET}"
#    elif cci <= -120:
#        cci_display = f"{GREEN}{round(cci, 2)}{RESET}"
#    else:
#        cci_display = f"{round(cci,2)}"
#
#    arrow = "🔼" if prev_cci is not None and cci > prev_cci else ("🔽" if prev_cci is not None and cci < prev_cci else "⏸️")
    #position_status = "📌 ACTIVE" if is_position_open_or_pending() else "📂 NONE"

#    print(f"{time_str} 📊 CCI14: {cci_display} | Prev: {round(prev_cci, 2) if prev_cci is not None else '—'} {arrow} | Mean: {round(avg_tp, 2)} | StdDev: {round(dev, 2)}")

#    prev_cci = cci
#    return cci

# === קביעת תאריך היום ואתמול ===
# === Define today's and yesterday's date ===
today = datetime.datetime.now().date()
yesterday = today - datetime.timedelta(days=1)

# === Fetch previous daily candle to determine market direction ===
bars_daily = ib.reqHistoricalData(
    contract,
    endDateTime=today.strftime('%Y%m%d 00:00:00'),
    durationStr='2 D',
    barSizeSetting='1 day',
    whatToShow='TRADES',
    useRTH=True
)

if len(bars_daily) < 2:
    print("⚠️ Not enough daily candles — exiting")
    sys.exit()

prev_bar = bars_daily[-2]
is_bullish = prev_bar.close > prev_bar.open
fib_high = prev_bar.high
fib_low = prev_bar.low

print(f"📅 Previous Candle: OPEN = {prev_bar.open} | CLOSE = {prev_bar.close} | {'POSITIVE' if is_bullish else 'NEGATIVE'}")

# === Calculate Fibonacci levels based on previous candle ===
fib_ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
fib_levels = [
    round(fib_low + (fib_high - fib_low) * r, 2) if is_bullish else round(fib_high - (fib_high - fib_low) * r, 2)
    for r in fib_ratios
]

print(f"📐 Fibonacci {'Support' if is_bullish else 'Resistance'} Levels: {fib_levels}")

# === Attempt to fetch 120 hourly candles ===
try:
    bars_hourly = ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr='120 H',
        barSizeSetting='1 hour',
        whatToShow='TRADES',
        useRTH=True
    )
except Exception as e:
    print(f"⚠️ Error fetching hourly candles: {e}")
    bars_hourly = []

# === Fallback: request 3 days of hourly candles ===
if len(bars_hourly) < 120:
    print("🔁 Fallback: requesting 3 days of hourly candles...")
    try:
        bars_hourly = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='3 D',
            barSizeSetting='1 hour',
            whatToShow='TRADES',
            useRTH=True
        )
    except Exception as e:
        print(f"❌ Fallback request failed: {e}")
        bars_hourly = []

# === Final check ===
if len(bars_hourly) < 120:
    ma_120_hourly = MANUAL_MA_120
    print(f"⚠️ Not enough hourly candles ({len(bars_hourly)}/120) — using manual override: {ma_120_hourly}")
else:
    hourly_closes = [bar.close for bar in bars_hourly[-120:]]
    ma_120_hourly = round(sum(hourly_closes) / len(hourly_closes), 4)
    print(f"📊 120-Hour Moving Average: {ma_120_hourly}")

# === Calculate 120-hour moving average ===
hourly_closes = [bar.close for bar in bars_hourly[-120:]]
ma_120_hourly = round(sum(hourly_closes) / len(hourly_closes), 4)
print(f"📊 120-Hour Moving Average: {ma_120_hourly}")

def check_long_condition(cci_values):
    return len(cci_values) >= 3 and cci_values[-3] < -120 and cci_values[-2] > -120 and cci_values[-1] > cci_values[-2] 

def check_short_condition(cci_values):
    return len(cci_values) >= 3 and cci_values[-3] >= 120 and cci_values[-2] < 120 and cci_values[-1] < cci_values[-2]

def is_position_open_or_pending(contract):
    """
    בודקת אם יש פוזיציה פתוחה או הוראה ממתינה על החוזה הנתון
    """
    for pos in ib.positions():
        if pos.contract.conId == contract.conId and pos.position != 0:
            return True

    for trade in ib.trades():
        if trade.contract.conId == contract.conId:
            status = trade.orderStatus.status
            transmit_flag = getattr(trade.order, 'transmit', True)
            if status not in ('Filled', 'Cancelled') and transmit_flag:
                return True

    return False

def safe_bracket_ticks(symbol, quantity, action='BUY'):
    global active_stop_price, active_direction, trade_active
    global active_sl_order_id, active_tp_order_id, active_tp_price

    if trade_active or is_position_open_or_pending(contract):
        print("⛔ Trade already active or position open — skipping bracket order")
        return False

    tick = ib.reqMktData(contract, snapshot=True)
    ib.sleep(1)
    ref_price = tick.last or tick.close or tick.ask or tick.bid

    if not isinstance(ref_price, (int, float)):
        print("⚠️ No valid price — skipping order")
        return False

    tp_ticks = TP_TICKS_LONG if action == 'BUY' else TP_TICKS_SHORT
    sl_ticks = SL_TICKS

    tp = round(ref_price + TICK_SIZE * (tp_ticks if action == 'BUY' else -tp_ticks), 2)
    sl = round(ref_price + TICK_SIZE * (-sl_ticks if action == 'BUY' else sl_ticks), 2)

    active_stop_price = sl
    active_tp_price = tp
    active_direction = 'LONG' if action == 'BUY' else 'SHORT'
    trade_active = True

    # === קביעת orderId ידני כדי לקשר את ההוראות
    entry_order_id = ib.client.getReqId()

    # === הוראת MARKET כניסה
    entry_order = MarketOrder(action, quantity)
    entry_order.transmit = False
    entry_order.orderId = entry_order_id
    ib.placeOrder(contract, entry_order)
    print(f"🚀 Entry MARKET order prepared: {entry_order_id} @ {ref_price}")

    # === הוראת SL
    sl_order = StopOrder('SELL' if action == 'BUY' else 'BUY', quantity, sl)
    sl_order.transmit = False
    sl_order.parentId = entry_order_id
    ib.placeOrder(contract, sl_order)
    print(f"📤 SL order prepared: {sl_order.orderId} @ {sl}")

    # === הוראת TP — משדרת את כל השרשרת
    tp_order = LimitOrder('SELL' if action == 'BUY' else 'BUY', quantity, tp)
    tp_order.transmit = True
    tp_order.parentId = entry_order_id
    ib.placeOrder(contract, tp_order)
    print(f"🎯 TP order sent: {tp_order.orderId} @ {tp}")

    active_sl_order_id = sl_order.orderId
    active_tp_order_id = tp_order.orderId

    print(f"✅ Bracket {action} order completed | Entry: {ref_price} | TP: {tp} | SL: {sl}")
    print(f"📌 Trade active: {trade_active} | Direction: {active_direction}")
    return True


def close_position_manually(contract, action):
    has_position = any(
        pos.contract.conId == contract.conId and pos.position != 0
        for pos in ib.positions()
    )

    active_sl_trade = None
    for trade in ib.trades():
        if trade.order.orderType == 'STP' and trade.contract.conId == contract.conId:
            if trade.orderStatus.status not in ('Filled', 'Cancelled'):
                active_sl_trade = trade
                break

    if has_position and active_sl_trade:
        tick = ib.reqMktData(contract, snapshot=True)
        ib.sleep(1)
        current_price = tick.last or tick.close or tick.ask or tick.bid

        sl_price = active_sl_trade.order.auxPrice
        if (
            (action == 'BUY' and current_price >= sl_price) or
            (action == 'SELL' and current_price <= sl_price)
        ):
            close_order = MarketOrder(action, QUANTITY)
            ib.placeOrder(contract, close_order)

            for order in ib.orders():
                ib.cancelOrder(order)

            print(f"❌ Manual close order sent: {action} @ market — all orders cancelled")
        else:
            print(f"ℹ️ Price has not crossed stop level — no manual close")
    else:
        print(f"ℹ️ No active position or stop order — skipping manual close")

def close_all_positions_and_orders():
    # סגירת פוזיציות פתוחות
    for pos in ib.positions():
        if pos.contract.symbol == 'CL' and pos.contract.lastTradeDateOrContractMonth == '202602':
            qty = abs(pos.position)
            if qty > 0:
                action = 'SELL' if pos.position > 0 else 'BUY'
                close_order = MarketOrder(action, qty)
                ib.placeOrder(pos.contract, close_order)
                print(f"❌ Closing position: {action} {qty} contracts")

    # ביטול הוראות פתוחות
    for order in ib.orders():
        ib.cancelOrder(order)
        print(f"🛑 Cancelling order ID: {order.orderId}")

    print("✅ All positions closed and orders cancelled")

def reset_trade_state():
    global active_direction, active_stop_price, trade_active
    global active_sl_order_id, active_tp_order_id

    active_direction = None
    active_stop_price = None
    trade_active = False
    active_sl_order_id = None
    active_tp_order_id = None

    print("🔄 Trade state reset — bot is idle")
    print(f"📌 Trade active: {trade_active} | Direction: {active_direction}")

# === לולאת מסחר ראשית ===
while True:
    now = datetime.datetime.now()
    hour = now.hour

    # === ניהול שעות מסחר כולל סגירה אוטומטית ===
    if not (7 <= hour < 23):
        if trade_active:
            print("🌙 Outside trading hours — closing active position")
            if active_direction == 'LONG':
                close_position_manually(contract, 'SELL')
            elif active_direction == 'SHORT':
                close_position_manually(contract, 'BUY')
            reset_trade_state()
            last_stop_direction = None
        elif not paused_notice_shown:
            print("⏸️ Outside trading hours — no action")
            paused_notice_shown = True

        time.sleep(CHECK_INTERVAL)
        continue

    paused_notice_shown = False

    # === משיכת מחיר נוכחי מה־IB Gateway ===
    tick = ib.reqMktData(contract, snapshot=True)
    ib.sleep(1)
    current_price = tick.last or tick.close or tick.ask or tick.bid
    if not isinstance(current_price, (int, float)):
        print("⚠️ Invalid price — skipping")
        time.sleep(CHECK_INTERVAL)
        continue

    # === עדכון היסטוריית מחירים לצורך EMA ו־MA120h ===
    price_history.append(current_price)
    if len(price_history) > EMA_SLOW_PERIOD:
        price_history = price_history[-EMA_SLOW_PERIOD:]

    hourly_closes.append(current_price)
    if len(hourly_closes) > 120:
        hourly_closes = hourly_closes[-120:]
    ma_120_hourly = round(sum(hourly_closes) / len(hourly_closes), 4)

    # === קביעת יעד פיבונאצי לפי נר אתמול ===
    if is_bullish:
        fib_target = fib_levels[3]
        planned_action = "LONG"
        fib_type = "Support"
        entry_condition_met = current_price <= fib_target
    else:
        fib_target = round(fib_high - (fib_high - fib_low) * 0.618, 2)
        planned_action = "SHORT"
        fib_type = "Resistance"
        entry_condition_met = current_price >= fib_target

    # === תנאי כניסה רגיל לפי נר אתמול ===
    if entry_condition_met and not trade_active and not is_position_open_or_pending(contract):
        print(f"⚡ Trade is about to be executed — price {current_price:.2f} meets {planned_action} condition at {fib_target:.2f}")
        entry_price = current_price
        if planned_action == "LONG":
            active_tp_price = round(entry_price + TICK_SIZE * TP_TICKS_LONG, 2)
            print(f"📈 LONG signal @ {entry_price:.2f} near 61.8% support {fib_target:.2f}")
            safe_bracket_ticks('CL', QUANTITY, action='BUY')
        else:
            active_tp_price = round(entry_price - TICK_SIZE * TP_TICKS_SHORT, 2)
            print(f"📉 SHORT signal @ {entry_price:.2f} near 61.8% resistance {fib_target:.2f}")
            safe_bracket_ticks('CL', QUANTITY, action='SELL')

    # === תנאי היפוך לאחר SL
    if last_stop_direction == 'LONG' and not trade_active and not is_position_open_or_pending(contract):
        if current_price >= fib_levels[3]:
            active_tp_price = round(current_price - TICK_SIZE * TP_TICKS_SHORT, 2)
            print(f"🔄 Reversal: Entering SHORT after failed LONG at {fib_levels[3]:.2f}")
            safe_bracket_ticks('CL', QUANTITY, action='SELL')
            last_stop_direction = None

    if last_stop_direction == 'SHORT' and not trade_active and not is_position_open_or_pending(contract):
        if current_price <= fib_target:
            active_tp_price = round(current_price + TICK_SIZE * TP_TICKS_LONG, 2)
            print(f"🔄 Reversal: Entering LONG after failed SHORT at {fib_target:.2f}")
            safe_bracket_ticks('CL', QUANTITY, action='BUY')
            last_stop_direction = None

    # === ניהול פוזיציה פתוחה — סגירה לפי TP או SL
    if trade_active:
        if active_direction == 'LONG':
            if current_price <= active_stop_price:
                print(f"🛑 SL hit at {current_price:.2f} — closing LONG")
                close_position_manually(contract, 'SELL')
                reset_trade_state()
                last_stop_direction = 'LONG'
            elif current_price >= active_tp_price:
                print(f"✅ TP hit at {current_price:.2f} — closing LONG")
                close_position_manually(contract, 'SELL')
                reset_trade_state()
        elif active_direction == 'SHORT':
            if current_price >= active_stop_price:
                print(f"🛑 SL hit at {current_price:.2f} — closing SHORT")
                close_position_manually(contract, 'BUY')
                reset_trade_state()
                last_stop_direction = 'SHORT'
            elif current_price <= active_tp_price:
                print(f"✅ TP hit at {current_price:.2f} — closing SHORT")
                close_position_manually(contract, 'BUY')
                reset_trade_state()

    # === הדפסת סטאטוס כללי בכל סיבוב
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-4]
    position_status = "ACTIVE" if trade_active else "IDLE"
    direction = active_direction if trade_active else "—"
    tp = active_tp_price if trade_active else "—"
    sl = active_stop_price if trade_active else "—"

    print(f"🕒 {timestamp} | Price: {current_price:.2f} | MA120h: {ma_120_hourly:.2f}")
    print(f"📐 Fibonacci {fib_type} Target: {fib_target:.2f} | Planned Action: {planned_action}")
    print(f"📌 Position: {position_status} | Direction: {direction} | TP: {tp} | SL: {sl}")
    print("—" * 60)

    time.sleep(CHECK_INTERVAL)