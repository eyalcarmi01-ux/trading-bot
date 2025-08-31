# CCI14DEC_V6.PY חוזה לדצמבר
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
SL_TICKS = 7 #17 after #7 premarket
TP_TICKS_LONG = 10 # 25 # 10
TP_TICKS_SHORT =10 # 35 # 10 
QUANTITY = 1

# === משתנים גלובליים ===
price_history = []
cci_values = []
prev_cci = None
ema_fast = ema_slow = None
paused_notice_shown = False
active_sl_price = None
active_sl_order_id = None
signal_action = None
signal_time = None
paused_notice_shown = False
trade_active = False
active_direction = None
pending_entry_order = None
pending_entry_action = None


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

ema_fast = ema_slow = initial_ema

# === התחברות ל־IB ===
ib = IB()
#contract = Future(symbol='ES', lastTradeDateOrContractMonth='202511', exchange='CME', currency='USD')
contract = Future(symbol='CL', lastTradeDateOrContractMonth='202512', exchange='NYMEX', currency='USD')
ib.connect('127.0.0.1', 7497, clientId=1)
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
print("🔍 Preparing CCI14 calculation: collecting price history...\n")
while len(price_history) < CCI_PERIOD:
    tick = ib.reqMktData(contract, snapshot=True)
    ib.sleep(CHECK_INTERVAL)
    price = tick.last or tick.close or tick.ask or tick.bid
    if isinstance(price, (int, float)):
        price_history.append(price)
        print(f"⏳ CCI History: {len(price_history)}/{CCI_PERIOD} collected")
    else:
        print("⚠️ Invalid price — skipping")

print("✅ CCI14 history complete — bot ready to start\n")

# === פונקציות עזר ===
def calculate_and_log_cci(prices, time_str):
    global prev_cci
    if len(prices) < CCI_PERIOD:
        print(f"{time_str} ⚠️ Not enough data for CCI")
        return None

    typical_prices = prices[-CCI_PERIOD:]
    avg_tp = mean(typical_prices)
    dev = stdev(typical_prices)

    if dev == 0:
        print(f"{time_str} ⚠️ StdDev is zero — CCI = 0")
        return 0

    cci = (typical_prices[-1] - avg_tp) / (0.015 * dev)
    arrow = "🔼" if prev_cci is not None and cci > prev_cci else ("🔽" if prev_cci is not None and cci < prev_cci else "⏸️")
    print(f"{time_str} 📊 CCI14: {round(cci,2)} | Prev: {round(prev_cci,2) if prev_cci else '—'} {arrow} | Mean: {round(avg_tp,2)} | StdDev: {round(dev,2)}")
    prev_cci = cci
    return cci

def send_bracket_order(contract, quantity, action='BUY'):
    global active_sl_price, active_sl_order_id, signal_action, trade_active

    time_str = datetime.datetime.now().strftime('%H:%M:%S')
    tick = ib.reqMktData(contract, snapshot=True)
    ib.sleep(1)
    ref_price = tick.last or tick.close or tick.ask or tick.bid

    if not isinstance(ref_price, (int, float)) or math.isnan(ref_price):
        print(f"{time_str} ⚠️ Invalid price — skipping bracket")
        return False

    tp_ticks = TP_TICKS_LONG if action == 'BUY' else TP_TICKS_SHORT
    tp = round(ref_price + TICK_SIZE * (tp_ticks if action == 'BUY' else -tp_ticks), 2)
    sl = round(ref_price + TICK_SIZE * (-SL_TICKS if action == 'BUY' else SL_TICKS), 2)

    entry_order = MarketOrder(action, quantity)
    entry_order.transmit = False
    ib.placeOrder(contract, entry_order)

    sl_order = StopOrder('SELL' if action == 'BUY' else 'BUY', quantity, sl)
    sl_order.transmit = False
    sl_order.parentId = entry_order.orderId
    ib.placeOrder(contract, sl_order)

    tp_order = LimitOrder('SELL' if action == 'BUY' else 'BUY', quantity, tp)
    tp_order.transmit = True
    tp_order.parentId = entry_order.orderId
    ib.placeOrder(contract, tp_order)

    active_sl_price = sl
    active_sl_order_id = sl_order.orderId
    signal_action = action
    trade_active = True

    print(f"{time_str} ✅ Bracket {action} sent | Entry: {ref_price} | TP: {tp} | SL: {sl}")
    return True

def is_position_open_or_pending(contract):
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

def check_stop_trigger(current_price, sl_price, action):
    if sl_price is None:
        return False

    if action == 'BUY' and current_price <= sl_price:
        return True

    if action == 'SELL' and current_price >= sl_price:
        return True

    return False

def handle_trading_hours(now, contract):
    global paused_notice_shown, active_sl_price, active_sl_order_id, signal_action, signal_time

    time_str = now.strftime('%H:%M:%S')

    # בדיקת טריגר לסטופ וסגירה ידנית אם צריך
    if active_sl_price is not None and active_sl_order_id is not None:
        for trade in ib.trades():
            if trade.order.orderId == active_sl_order_id:
                status = trade.orderStatus.status

                if status == 'Filled':
                    print(f"{time_str} ✅ Stop order filled — position closed")
                    active_sl_price = None
                    active_sl_order_id = None
                    signal_action = None
                    signal_time = None
                    trade_active = False
                    active_direction = None
                    break

                elif status not in ('Cancelled', 'Filled'):
                    tick = ib.reqMktData(contract, snapshot=True)
                    ib.sleep(1)
                    current_price = tick.last or tick.close or tick.ask or tick.bid
                    if check_stop_trigger(current_price, active_sl_price, signal_action):
                        print(f"{time_str} ⚠️ Manual stop triggered — closing position")
                        close_action = 'SELL' if signal_action == 'BUY' else 'BUY'
                        close_order = MarketOrder(close_action, QUANTITY)
                        ib.placeOrder(contract, close_order)
                        active_sl_price = None
                        active_sl_order_id = None
                        signal_action = None
                        signal_time = None
                        trade_active = False
                        active_direction = None
                        break

    # סגירה ב־22:50
    if now.hour == 22 and now.minute == 50:
        print(f"{time_str} 🛑 Market close triggered — cancelling orders and closing positions")

        for order in ib.orders():
            ib.cancelOrder(order)
            print(f"{time_str} ❌ Cancelled order ID: {order.orderId}")

        for pos in ib.positions():
            if pos.contract.conId == contract.conId and pos.position != 0:
                close_action = 'SELL' if pos.position > 0 else 'BUY'
                close_order = MarketOrder(close_action, abs(pos.position))
                ib.placeOrder(pos.contract, close_order)
                print(f"{time_str} ❌ Closed position: {close_action} {abs(pos.position)}")

        print(f"{time_str} ✅ All positions and orders closed — bot paused until 08:00")
        return 'pause'

    # חסימת מסחר בין 22:30 ל־08:00
    if (now.hour == 22 and now.minute >= 30) or now.hour < 8:
        if not paused_notice_shown:
            print(f"{time_str} 💤 Trading paused — waiting for 08:00")
            paused_notice_shown = True
        return 'pause'

    # חידוש מסחר בבוקר
    if paused_notice_shown and now.hour >= 8:
        print(f"{time_str} 🌅 Trading resumed — good morning!")
        paused_notice_shown = False

    return 'active'

print(f"🤖 Bot Running | EMA Fast: {EMA_FAST_PERIOD} | Slow: {EMA_SLOW_PERIOD} | Interval: {CHECK_INTERVAL}s\n")
last_minute = -1

while True:
    now = datetime.datetime.now()
    current_minute = now.minute

    if current_minute == last_minute:
        time.sleep(1)
        continue
    last_minute = current_minute
    time_str = now.strftime('%H:%M:%S')

    # === שעות מסחר ===
    status = handle_trading_hours(now, contract)
    if status == 'pause':
        continue

    # === בדיקת מצב פוזיציה ===
    previous_trade_status = trade_active
    trade_active = is_position_open_or_pending(contract)
    if trade_active and not previous_trade_status:
        print(f"{time_str} 🟢 Trade just opened — bot in active position")
    elif not trade_active and previous_trade_status:
        print(f"{time_str} 🔄 Trade closed — bot ready for next opportunity")

    # === מחיר נוכחי ===
    tick = ib.reqMktData(contract, snapshot=True)
    ib.sleep(1)
    price = tick.last or tick.close or tick.ask or tick.bid
    if not isinstance(price, (int, float)) or math.isnan(price):
        print(f"{time_str} ⚠️ Invalid price — skipping\n")
        continue

    # === חישוב EMA ===
    ema_fast = round(price * K_FAST + ema_fast * (1 - K_FAST), 4)
    ema_slow = round(price * K_SLOW + ema_slow * (1 - K_SLOW), 4)
    print(f"{time_str} 💹 Price: {price} | EMA10: {ema_fast} | EMA200: {ema_slow}")

    # === חישוב CCI ===
    price_history.append(price)
    if len(price_history) >= CCI_PERIOD:
        cci = calculate_and_log_cci(price_history, time_str)
        if cci is not None:
            cci_values.append(cci)
            if len(cci_values) > 100:
                cci_values = cci_values[-100:]
    if len(price_history) > 500:
        price_history = price_history[-500:]

    # === חסימה אם יש פוזיציה פעילה ===
    if trade_active:
        print(f"{time_str} 🚫 BLOCKED: Trade already active\n")
        continue

    # === איתור סיגנל ===
    if len(cci_values) >= 2 and signal_time is None:
        prev_cci = cci_values[-2]
        curr_cci = cci_values[-1]

        if prev_cci < 0 < curr_cci and price > ema_fast:
            signal_time = now
            signal_action = 'BUY'
            print(f"{time_str} ⏳ BUY signal detected — waiting 3 minutes")

        elif prev_cci > 0 > curr_cci and price < ema_fast:
            signal_time = now
            signal_action = 'SELL'
            print(f"{time_str} ⏳ SELL signal detected — waiting 3 minutes")

        else:
            print(f"{time_str} 🔍 No valid signal — conditions not met\n")

    # === לאחר 3 דקות — שליחת הבראקט
    if signal_time is not None:
        elapsed = (datetime.datetime.now() - signal_time).total_seconds()
        if elapsed >= 180:
            success = send_bracket_order(contract, QUANTITY, action=signal_action)
            if success:
                print(f"{time_str} ✅ Bracket sent — bot in active position\n")
                signal_time = None
                signal_action = None
            else:
                print(f"{time_str} ❌ Failed to send bracket — retrying next tick\n")
        else:
            remaining = round(180 - elapsed)
            print(f"{time_str} ⏳ Waiting {remaining}s before sending bracket\n")

# CODE END HERE #


#29.08.25 לבדוק סגירה של עסקאות ב 22:50. לבדוק סטאפ פרמטרים להוראות מסחר. לבדוק תזמונים כניסה לעסקה