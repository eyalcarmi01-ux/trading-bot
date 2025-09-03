# cci14rev2.6.py חוזה לנובמבר
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
contract = Future(symbol='CL', lastTradeDateOrContractMonth='202511', exchange='NYMEX', currency='USD')
#contract = Future(symbol='CL', lastTradeDateOrContractMonth='202510', exchange='NYMEX', currency='USD')
ib.connect('127.0.0.1', 7497, clientId=18)
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

# === אתחול EMA200 מתוך ערך קבוע ===
ema_slow = initial_ema

# === חישוב EMA10 מתוך 10 המחירים האחרונים ===
recent_prices = price_history[-EMA_FAST_PERIOD:]
ema_fast = recent_prices[0]  # התחלה

for price in recent_prices[1:]:
    ema_fast = round(price * K_FAST + ema_fast * (1 - K_FAST), 4)
print(f"📊 EMA10 source prices: {recent_prices}")

print(f"📈 Initial EMA10 calculated from history: {ema_fast}")

# === צבעים למסך (ANSI Terminal Codes) ===
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# === פונקציות עזר מחזירה ערך prev_cci===
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

    if cci >= 120:
        cci_display = f"{RED}{round(cci, 2)}{RESET}"
    elif cci <= -120:
        cci_display = f"{GREEN}{round(cci, 2)}{RESET}"
    else:
        cci_display = f"{round(cci,2)}"

    arrow = "🔼" if prev_cci is not None and cci > prev_cci else ("🔽" if prev_cci is not None and cci < prev_cci else "⏸️")
    #position_status = "📌 ACTIVE" if is_position_open_or_pending() else "📂 NONE"

    print(f"{time_str} 📊 CCI14: {cci_display} | Prev: {round(prev_cci, 2) if prev_cci is not None else '—'} {arrow} | Mean: {round(avg_tp, 2)} | StdDev: {round(dev, 2)}")

    prev_cci = cci
    return cci

def check_long_condition(cci_values):
    return len(cci_values) >= 3 and cci_values[-3] < -120 and cci_values[-2] > -120 and cci_values[-1] > cci_values[-2] 

def check_short_condition(cci_values):
    return len(cci_values) >= 3 and cci_values[-3] >= 120 and cci_values[-2] < 120 and cci_values[-1] < cci_values[-2]

def safe_bracket_ticks(symbol, quantity, action='BUY'):
    global active_stop_price, active_direction, trade_active
    global active_sl_order_id, active_tp_order_id

    if trade_active or is_position_open_or_pending():
        print("⛔ Trade already active or position open — skipping bracket order")
        return False

    global contract
    #contract = Future(symbol=symbol, lastTradeDateOrContractMonth='202511', exchange='NYMEX', currency='USD')
    tick = ib.reqMktData(contract, snapshot=True)
    ib.sleep(1)
    ref_price = tick.last or tick.close or tick.ask or tick.bid

    if not isinstance(ref_price, (int, float)):
        print("⚠️ No valid price — skipping order")
        return False

    tp_ticks = TP_TICKS_LONG if action == 'BUY' else TP_TICKS_SHORT
    tp = round(ref_price + TICK_SIZE * (tp_ticks if action == 'BUY' else -tp_ticks), 2)
    sl = round(ref_price + TICK_SIZE * (-SL_TICKS if action == 'BUY' else SL_TICKS), 2)

    active_stop_price = sl
    active_direction = 'LONG' if action == 'BUY' else 'SHORT'
    trade_active = True

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

    active_sl_order_id = sl_order.orderId
    active_tp_order_id = tp_order.orderId

    print(f"✅ Bracket {action} order sent | Entry: {ref_price} | TP: {tp} | SL: {sl}")
    print(f"📌 Trade active: {trade_active} | Direction: {active_direction}")
    return True

def is_position_open_or_pending():
    for pos in ib.positions():
        if pos.contract.symbol == 'CL' and pos.contract.lastTradeDateOrContractMonth == '202511':
            if pos.position != 0:
                return True
    for trade in ib.trades():
        if trade.contract.symbol == 'CL' and trade.orderStatus.status not in ('Filled', 'Cancelled'):
            return True
    return False

#cci_values = []

def close_position_manually(contract, action):
    # בדיקה אם יש פוזיציה פתוחה
    has_position = any(
        pos.contract.symbol == contract.symbol and
        pos.contract.lastTradeDateOrContractMonth == contract.lastTradeDateOrContractMonth and
        pos.position != 0
        for pos in ib.positions()
    )

    # בדיקה אם הוראת סטופ קיימת ופעילה
    active_sl_trade = None
    for trade in ib.trades():
        if trade.order.orderType == 'STP' and trade.contract.symbol == contract.symbol:
            if trade.orderStatus.status not in ('Filled', 'Cancelled'):
                active_sl_trade = trade
                break

    # תנאי סגירה ידנית
    if has_position and active_sl_trade:
        tick = ib.reqMktData(contract, snapshot=True)
        ib.sleep(1)
        current_price = tick.last or tick.close or tick.ask or tick.bid

        # בדיקה אם המחיר עבר את הסטופ
        sl_price = active_sl_trade.order.auxPrice
        if (
            (action == 'BUY' and current_price >= sl_price) or
            (action == 'SELL' and current_price <= sl_price)
        ):
            close_order = MarketOrder(action, QUANTITY)
            ib.placeOrder(contract, close_order)

            # ביטול כל ההוראות הפתוחות
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
        if pos.contract.symbol == 'CL' and pos.contract.lastTradeDateOrContractMonth == '202511':
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
    
# === פונקציית הריצה הראשית ===
def run_bot_cycle():
    global ema_fast, ema_slow, prev_cci, paused_notice_shown, trade_active
    global cci_values, price_history, active_direction, active_stop_price
    global active_sl_order_id, active_tp_order_id

    now = datetime.datetime.now()
    time_str = now.strftime('%H:%M:%S')

    # 📈 משיכת מחיר שוק
    tick = ib.reqMktData(contract, snapshot=True)
    ib.sleep(1)
    price = tick.last or tick.close or tick.ask or tick.bid

    # 🧠 בדיקה אם הוראת TP או SL מולאה — לפי מזהה
    if active_sl_order_id or active_tp_order_id:
        for trade in ib.trades():
            if trade.orderStatus.status == 'Filled':
                if trade.order.orderId == active_sl_order_id:
                    print(f"{time_str} ✅ SL filled @ {trade.order.auxPrice} — resetting state")
                    reset_trade_state()
                    break
                elif trade.order.orderId == active_tp_order_id:
                    print(f"{time_str} ✅ TP filled @ {trade.order.lmtPrice} — resetting state")
                    reset_trade_state()
                    break

    if not isinstance(price, (int, float)) or math.isnan(price):
        print(f"{time_str} ⚠️ Invalid price — skipping\n")
        return

    # 📉 חישוב EMA
    ema_fast = round(price * K_FAST + ema_fast * (1 - K_FAST), 4)
    ema_slow = round(price * K_SLOW + ema_slow * (1 - K_SLOW), 4)
    ema10 = ema_fast
    ema200 = ema_slow

    # 📊 חישוב CCI
    price_history.append(price)
    price_history = price_history[-CCI_PERIOD:]
    cci = calculate_and_log_cci(price_history, time_str)
    if cci is not None:
        cci_values.append(cci)
        cci_values = cci_values[-100:]

    # 🕒 ניהול שעות מסחר
    if now.hour == 22 and now.minute == 50:
        print(f"{time_str} 🕒 22:50 — closing all positions before shutdown")
        close_all_positions_and_orders()
        reset_trade_state()
        print(f"{time_str} 💤 Trading day ended — bot shutting down")
        sys.exit()

    elif now.hour == 22 and now.minute == 30 and not paused_notice_shown:
        print(f"{time_str} 🚫 TRADING CLOSED FOR NEW ORDERS — monitoring existing positions only")
        paused_notice_shown = True
        return

    elif now.hour < 8:
        if not paused_notice_shown:
            print(f"{time_str} 💤 Trading paused until 08:00")
            paused_notice_shown = True
        return

    elif now.hour == 8 and now.minute == 0:
        print(f"{time_str} 🌅 TRADING RESUMED — bot active")
        paused_notice_shown = False
    else:
        paused_notice_shown = False

    print(f"{time_str} 💹 Price: {price:.2f} | EMA10: {ema10:.4f} | EMA200: {ema200:.4f}")

    if cci is not None:
        prev_cci_val = cci_values[-2] if len(cci_values) >= 2 else None
        arrow = "🔼" if prev_cci_val and cci > prev_cci_val else "🔽" if prev_cci_val and cci < prev_cci_val else "⏸️"
        mean_price = round(mean(price_history), 2)
        std_dev = round(stdev(price_history), 2)
        print(f"{time_str} 📊 CCI14: {round(cci,2)} | Prev: {round(prev_cci_val,2) if prev_cci_val else '—'} {arrow} | Mean: {mean_price} | StdDev: {std_dev} | 📌 ACTIVE ({active_direction})")

    # 📌 בדיקת מצב פוזיציה
    trade_active = is_position_open_or_pending()

    # 🛑 בדיקת סטופ ידני
    if active_direction in ["LONG", "SHORT"] and active_stop_price is not None:
        if active_direction == "LONG" and price <= active_stop_price:
            print(f"{time_str} 🛑 Price hit LONG stop @ {price:.2f} — closing manually")
            close_position_manually(contract, "SELL")
            reset_trade_state()
            return
        elif active_direction == "SHORT" and price >= active_stop_price:
            print(f"{time_str} 🛑 Price hit SHORT stop @ {price:.2f} — closing manually")
            close_position_manually(contract, "BUY")
            reset_trade_state()
            return

    # 🧹 איפוס מצב אם אין פוזיציה בפועל
    if not is_position_open_or_pending() and trade_active:
        print(f"{time_str} 🔄 No position detected — resetting trade state")
        reset_trade_state()

    # ✅ תנאים לכניסה לעסקה — רק אם אין עסקה פעילה
    if not trade_active and active_direction is None:
        print(f"{time_str} 🔎 Checking entry conditions...")
        if ema_fast > ema_slow and check_long_condition(cci_values):
            if safe_bracket_ticks('CL', QUANTITY, action='BUY'):
                trade_active = True
                active_direction = "LONG"
                print(f"{time_str} ✅ LONG signal confirmed — trade opened\n")
        elif ema_fast < ema_slow and check_short_condition(cci_values):
            if safe_bracket_ticks('CL', QUANTITY, action='SELL'):
                trade_active = True
                active_direction = "SHORT"
                print(f"{time_str} ✅ SHORT signal confirmed — trade opened\n")
        else:
            print(f"{time_str} 🔍 No valid signal — conditions not met\n")
    else:
        print(f"{time_str} 🟢 TRADE ACTIVE — bot in position")
        print(f"{time_str} 🔍 No valid signal — monitoring position\n")

while True:
    run_bot_cycle()
    ib.sleep(CHECK_INTERVAL)

    # גרסה מוצלחת - להמשיך להריץ 08.08.25
    #לבדוק איך למשוך נתונים היסטוריים במקום לחשב 14 דקות שלמות
    #  לסדר הדפסות כפולות בלוג. שורה 122, לבדוק הוראה סטופ נתפסת לפני תחילת המסחר
    # הוראות לא נסגרות ב 22:50
    #11.08.25 להמשיך להריץ - שונה לחוזה נובמבר!
    #12.08.25 להמשיך להריץ    # יש באג - עסקה נסגרת והקוד לא מאפס את הפוזיציה ואין עסקאות חדשות 
    # רץ על חוזה לנובמבר - איפוס פוזיציה לא עובד טוב וגם מוניטור אחרי מחיר ביחס לסטופ
    # גרסה מצולחת. הסטופ מתנהל בפרה-מארקט היטב. יש שגיאות של הוראות שצריך לבדוק. להמשיך להריץ. 27.08.28
    # לבדוק סגירה של פוזיציות וחסימה  מסחר אחרי 22:30