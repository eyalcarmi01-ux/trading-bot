from ib_insync import *
import datetime, time, math

class TradingAlgorithm:
    def __init__(self, contract_params, ib_host='127.0.0.1', ib_port=7497, client_id=17):
        self.ib = IB()
        self.contract = Future(**contract_params)
        self.ib.connect(ib_host, ib_port, clientId=client_id)
        self.ib.qualifyContracts(self.contract)
        print("✅ Connected to IB Gateway")
        self.current_sl_price = None

    def place_bracket_order(self, action, quantity, tick_size, sl_ticks, tp_ticks_long, tp_ticks_short):
        # ...existing code for safe_bracket_ticks, adapted to class...
        pass

    def monitor_stop(self, positions):
        # ...existing code for monitor_stop, adapted to class...
        pass

    def cancel_all_orders(self):
        for order in self.ib.orders():
            self.ib.cancelOrder(order)

    def close_all_positions(self):
        positions = self.ib.positions()
        for p in positions:
            if abs(p.position) > 0:
                action = 'SELL' if p.position > 0 else 'BUY'
                close_order = MarketOrder(action, abs(p.position))
                self.ib.placeOrder(p.contract, close_order)

    def reconnect(self):
        self.ib.disconnect()
        time.sleep(2)
        self.ib.connect('127.0.0.1', 7497, clientId=17)
        self.ib.qualifyContracts(self.contract)
        print("🔄 Reconnected to IB")

    def run(self):
        raise NotImplementedError("Subclasses must implement run()")

class EMATradingAlgorithm(TradingAlgorithm):
    def __init__(self, contract_params, ema_period, check_interval, initial_ema, signal_override, **kwargs):
        super().__init__(contract_params, **kwargs)
        self.EMA_PERIOD = ema_period
        self.K = 2 / (self.EMA_PERIOD + 1)
        self.CHECK_INTERVAL = check_interval
        self.live_ema = initial_ema
        self.signal_override = signal_override
        self.long_ready = self.short_ready = False
        self.long_counter = self.short_counter = 0
        self.paused_notice_shown = False
        self.TICK_SIZE = 0.01
        self.SL_TICKS = 17
        self.TP_TICKS_LONG = 28
        self.TP_TICKS_SHORT = 35
        self.QUANTITY = 1

    def run(self):
        # ...main loop logic from main_v7.1.py, adapted to class...
        pass

# Example usage (in main.py):
# contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
# algo = EMATradingAlgorithm(contract_params, ema_period=200, check_interval=60, initial_ema=..., signal_override=...)
# algo.run()
