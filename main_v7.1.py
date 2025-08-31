# python main_v7.py price 60 ema200 ovverride חוזה לינואר
from ib_insync import *
import datetime, time, sys, math

EMA_PERIOD = 200
K = 2 / (EMA_PERIOD + 1)

# === קלט מהשורת הרצה ===
if len(sys.argv) >= 5:
    cli_price = float(sys.argv[1])
    CHECK_INTERVAL = int(sys.argv[2])
    initial_ema = float(sys.argv[3])
    signal_override = int(sys.argv[4])
else:
    print("⚠️ Usage: python bot.py <price> <interval> <initial_ema> <signal_override>")
    sys.exit()

# === התחברות ל־IB ===
ib = IB()
contract = Future(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
ib.connect('127.0.0.1', 7497, clientId=17)
ib.qualifyContracts(contract)
print("✅ Connected to IB Gateway")

        
# === TEST ORDER לבדוק תקשורת ===
test_price = round(cli_price / 2, 2)
print(f"🧪 TEST order sent @ {test_price}")
test_order = LimitOrder('BUY', 1, test_price)
ib.placeOrder(contract, test_order)
ib.sleep(5)
ib.cancelOrder(test_order)
print("✅ TEST ORDER SENT AND CANCELLED SUCCESSFULLY\n")

# === מאפיינים כלליים למסחר ===
TICK_SIZE = 0.01
SL_TICKS = 17 #7
TP_TICKS_LONG = 28# 10
TP_TICKS_SHORT = 35# 10
QUANTITY = 1

live_ema = initial_ema
long_ready = short_ready = False
long_counter = short_counter = 0
paused_notice_shown = False
current_sl_price = None

# === חכה לתחילת דקה עגולה ===
now = datetime.datetime.now()
wait_sec = 60 - now.second
print(f"⏳ Waiting {wait_sec} seconds for round-minute start...")
time.sleep(wait_sec)
print(f"🚀 Starting at {datetime.datetime.now().strftime('%H:%M:%S')}\n")

def calculate_targets(side, price):
    tick_tp = TP_TICKS_SHORT if side == 'SELL' else TP_TICKS_LONG
    tp = round(price + TICK_SIZE * tick_tp * (-1 if side == 'SELL' else 1), 2)
    sl = round(price + TICK_SIZE * SL_TICKS * (-1 if side == 'SELL' else 1), 2)
    return tp, sl

# === פונקציה לפתיחת פוזיציה כולל TP ו־SL ===
def safe_bracket_ticks(symbol, quantity, action='BUY',
                       tick_size=0.01, sl_ticks=7,
                       tp_ticks_long=10, tp_ticks_short=10):

    contract = Future(symbol=symbol,
                      lastTradeDateOrContractMonth='202601',
                      exchange='NYMEX',
                      currency='USD')

    # === מחיר התייחסות מיידי (ללא המתנה ל־FILL) ===
    tick = ib.reqMktData(contract, snapshot=True)
    ib.sleep(1)
    ref_price = tick.last or tick.close or tick.ask or tick.bid

    if not isinstance(ref_price, (int, float)):
        print("⚠️ No valid price — skipping order")
        return

    # === חישוב TP/SL לפי כיוון ===
    if action.upper() == 'BUY':
        tp_price = round(ref_price + tick_size * tp_ticks_long, 2)
        sl_price = round(ref_price - tick_size * sl_ticks, 2)
        exit_action = 'SELL'
    elif action.upper() == 'SELL':
        tp_price = round(ref_price - tick_size * tp_ticks_short, 2)
        sl_price = round(ref_price + tick_size * sl_ticks, 2)
        exit_action = 'BUY'
    else:
        print("⚠️ Invalid action")
        return

    print(f"📌 Entry ref price: {ref_price}")
    print(f"🎯 TP: {tp_price} | 🛡️ SL: {sl_price}") 
    
    
    global current_sl_price
    current_sl_price = sl_price

    # === הוראות משורשרות (transmit = False לכל חוץ מהאחרון) ===
    entry_order = MarketOrder(action, quantity)
    entry_order.transmit = False
    ib.placeOrder(contract, entry_order)

    sl_order = StopOrder(exit_action, quantity, sl_price)
    sl_order.transmit = False
    sl_order.parentId = entry_order.orderId
    ib.placeOrder(contract, sl_order)

    tp_order = LimitOrder(exit_action, quantity, tp_price)
    tp_order.transmit = True  # זו ההוראה שמבצעת את כל השרשרת
    tp_order.parentId = entry_order.orderId
    ib.placeOrder(contract, tp_order)

    print(f"✅ Bracket order sent for {symbol} ({action})")

def monitor_stop(ib, contract, current_sl_price, positions):
    tick = ib.reqMktData(contract, snapshot=True)
    ib.sleep(1)
    market_price = tick.last or tick.close or tick.ask or tick.bid

    for p in positions:
        if p.contract.conId != contract.conId:
            continue

        position_side = 'LONG' if p.position > 0 else 'SHORT'
        sl_hit = (
            position_side == 'LONG' and market_price <= current_sl_price or
            position_side == 'SHORT' and market_price >= current_sl_price
        )

        if sl_hit:
            print(f"⚠️ Stop breached @ {market_price} vs SL {current_sl_price}")
            ib.sleep(5)

            # === סגירת פוזיציה ידנית עם חוזה מוכשר ===
            action = 'SELL' if p.position > 0 else 'BUY'
            close_contract = p.contract

            # תיקון: לוודא שהחוזה כולל exchange ומוכשר
            if not close_contract.exchange:
                close_contract.exchange = contract.exchange  # לדוגמה: 'NYMEX'
            ib.qualifyContracts(close_contract)

            close_order = MarketOrder(action, abs(p.position))
            ib.placeOrder(close_contract, close_order)
            print(f"❌ Manual close: {action} {abs(p.position)}")

            # === ביטול כל ההוראות הפתוחות
            for order in ib.orders():
                ib.cancelOrder(order)
            print("❌ All open orders cancelled after SL breach")

            return None  # איפוס ערך ה־SL

    return current_sl_price  # אם לא נפרץ, מחזיר את אותו ערך

# === הלולאה הראשית של הבוט ===
print(f"🤖 Bot Running | EMA Period: {EMA_PERIOD} | Interval: {CHECK_INTERVAL}s")

while True:
    try:
        ib.sleep(CHECK_INTERVAL)
        now = datetime.datetime.now()
        time_str = now.strftime('%H:%M:%S')

        # === הפסקת מסחר בין 22:30 ל־08:00 ===
        if (now.hour == 22 and now.minute >= 30) or now.hour < 7:
            if now.hour == 22 and now.minute == 50:
                for order in ib.orders():
                    ib.cancelOrder(order)
                print(f"{time_str} ❌ All open orders cancelled")

                positions = ib.positions()
                for p in positions:
                    if abs(p.position) > 0:
                        action = 'SELL' if p.position > 0 else 'BUY'
                        close_order = MarketOrder(action, abs(p.position))
                        ib.placeOrder(p.contract, close_order)
                        print(f"{time_str} ❌ Position closed: {action} {abs(p.position)} {p.contract.symbol}")

                print(f"{time_str} 🛑 Trading shutdown executed at 22:50")

            elif not paused_notice_shown:
                print(f"{time_str} 💤 Trading paused until 08:00")
                paused_notice_shown = True

            continue
        else:
            paused_notice_shown = False

        # === עדכון מחיר ו־EMA
        tick = ib.reqMktData(contract, snapshot=True)
        ib.sleep(1)
        price = tick.last or tick.close or tick.ask or tick.bid
        if not isinstance(price, (int, float)) or math.isnan(price):
            print(f"{time_str} ⚠️ Invalid price — skipping")
            continue

        previous_ema = live_ema
        live_ema = round(price * K + previous_ema * (1 - K), 4)
        print(f"{time_str} 📊 Price: {price} | EMA: {live_ema}")

        # === בדיקת פוזיציה פתוחה
        positions = ib.positions()
        active = any(p.contract.conId == contract.conId and abs(p.position) > 0 for p in positions)
        if active and current_sl_price is not None:
            positions = ib.positions()
            current_sl_price = monitor_stop(ib, contract, current_sl_price, positions)
        if active:
            print(f"{time_str} 🔒 Position active — monitoring only")
            continue

        # === ניהול override
        if signal_override == 1 and price < live_ema:
            print(f"{time_str} ⏩ Buy signal")
            signal_override = 0
            long_ready = True
            continue
        elif signal_override == -1 and price > live_ema:
            print(f"{time_str} ⏩ Sell signal")
            signal_override = 0
            short_ready = True
            continue

        if signal_override == 1:
            if long_counter == 0:
                long_counter = 15
                print(f"{time_str} ⏩ LONG override initialized | long_counter: {long_counter}")
            elif price > live_ema:
                long_counter += 1
                short_counter = 0
                print(f"{time_str} ⏳ LONG override counting | long_counter: {long_counter}")
                if long_counter >= 15 and not long_ready:
                    long_ready = True
                    print(f"{time_str} ✅ LONG setup ready [override]")
            elif price < live_ema:
                safe_bracket_ticks('CL', QUANTITY, action='BUY',
                                   tick_size=TICK_SIZE, sl_ticks=SL_TICKS,
                                   tp_ticks_long=TP_TICKS_LONG, tp_ticks_short=TP_TICKS_SHORT)
                long_ready = False
                long_counter = 0
                signal_override = 0
                print(f"{time_str} ✅ LONG override entry executed @ {price}")
            continue

        if signal_override == -1:
            if short_counter == 0:
                short_counter = 15
                print(f"{time_str} ⏩ SHORT override initialized | short_counter: {short_counter}")
            elif price < live_ema:
                short_counter += 1
                long_counter = 0
                print(f"{time_str} ⏳ SHORT override counting | short_counter: {short_counter}")
                if short_counter >= 15 and not short_ready:
                    short_ready = True
                    print(f"{time_str} ✅ SHORT setup ready [override]")
            elif price > live_ema:
                safe_bracket_ticks('CL', QUANTITY, action='SELL',
                                   tick_size=TICK_SIZE, sl_ticks=SL_TICKS,
                                   tp_ticks_long=TP_TICKS_LONG, tp_ticks_short=TP_TICKS_SHORT)
                short_ready = False
                short_counter = 0
                signal_override = 0
                print(f"{time_str} ✅ SHORT override entry executed @ {price}")
            continue

        # === ניתוח מגמה רגילה
        if price > live_ema:
            long_counter += 1
            short_counter = 0
            print(f"{time_str} 📈 LONG candle #{long_counter}")
            if long_counter >= 15 and not long_ready:
                long_ready = True
                print(f"{time_str} ✅ LONG setup ready")
        elif price < live_ema:
            short_counter += 1
            long_counter = 0
            print(f"{time_str} 📉 SHORT candle #{short_counter}")
            if short_counter >= 15 and not short_ready:
                short_ready = True
                print(f"{time_str} ✅ SHORT setup ready")
        else:
            print(f"{time_str} ⚖️ NEUTRAL candle — counters reset")

        # === כניסה לפוזיציה רגילה
        if long_ready and not active and price < live_ema:
            safe_bracket_ticks('CL', QUANTITY, action='BUY',
                               tick_size=TICK_SIZE, sl_ticks=SL_TICKS,
                               tp_ticks_long=TP_TICKS_LONG, tp_ticks_short=TP_TICKS_SHORT)
            long_ready = False
            long_counter = 0
            signal_override = 0

        elif short_ready and not active and price > live_ema:
            safe_bracket_ticks('CL', QUANTITY, action='SELL',
                               tick_size=TICK_SIZE, sl_ticks=SL_TICKS,
                               tp_ticks_long=TP_TICKS_LONG, tp_ticks_short=TP_TICKS_SHORT)
            short_ready = False
            short_counter = 0
            signal_override = 0

        else:
            print(f"{time_str} 🔍 No valid signal")

    except Exception as e:
        print(f"{datetime.datetime.now().strftime('%H:%M:%S')} ❌ Error: {e}")
        ib.disconnect()
        time.sleep(2)
        ib.connect('127.0.0.1', 7497, clientId=17)
        ib.qualifyContracts(contract)
        print("🔄 Reconnected to IB")

        signal_override = 0
        long_ready = False
        short_ready = False

# === ✅ END OF CODE ✅ ===

#29.08.25.לבדוק מה קורה עם פוזיציות בשעה 22:50
#עדכון ערכים של הוראות מסחרץ לבדוק ערכים לפרהמארקט, לבדוק רכים למסחר פעיל