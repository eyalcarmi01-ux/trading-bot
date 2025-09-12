from unittest.mock import MagicMock
import time


class MockIB:
    def __init__(self):
        self._orders = []  # list of order objects
        self._positions = []
        self.connected = False
        self.last_order = None
        # Performance counters
        self.call_count = 0
        self.call_times = []
        # Optional injection for historical data scenarios
        self._historical_overrides = {}
        # Trades list to emulate ib.trades()
        self._trades = []

    # --- IB-like methods used by tests/algorithms ---
    def connect(self, *a, **kw):
        self.connected = True

    def disconnect(self):
        self.connected = False

    # Align with ib_insync IB interface used in algorithms
    def isConnected(self):
        return self.connected

    def qualifyContracts(self, contract):
        self.call_count += 1
        return [contract]

    def reqMktData(self, contract, snapshot=True):
        # Track calls for performance tests
        self.call_count += 1
        self.call_times.append(time.time())
        # Return a simple tick-like object
        return MagicMock(last=100.0, close=100.0, ask=100.0, bid=100.0)

    def sleep(self, seconds):
        # Keep sleeps short in tests
        time.sleep(min(seconds, 0.1))

    def positions(self):
        self.call_count += 1
        return self._positions

    def placeOrder(self, contract, order):
        self.call_count += 1
        # emulate IB assigning an orderId onto the order object itself
        try:
            existing_id = getattr(order, 'orderId', None)
        except Exception:
            existing_id = None
        if not existing_id:
            order.orderId = len(self._orders) + 1
        self._orders.append(order)
        self.last_order = order
        return order

    def orders(self):
        return list(self._orders)

    def cancelOrder(self, order):
        pass

    def trades(self):
        # Return a shallow copy to avoid external mutation during iteration
        return list(self._trades)

    # --- Historical data emulation used by Fibonacci legacy mode ---
    class _Bar:
        def __init__(self, open_, high, low, close):
            self.open = open_
            self.high = high
            self.low = low
            self.close = close

    def reqHistoricalData(self, contract, endDateTime='', durationStr='', barSizeSetting='', whatToShow='TRADES', useRTH=True):
        # Allow tests to override by (durationStr, barSizeSetting) key
        key = (durationStr or '', barSizeSetting or '')
        if key in self._historical_overrides:
            return self._historical_overrides[key]
        # Defaults: 2 daily bars and 120 hourly bars with simple values
        if barSizeSetting == '1 day':
            # Two days: day-2 open/close lower, day-1 higher to be bullish
            return [
                self._Bar(100.0, 110.0, 95.0, 105.0),  # older
                self._Bar(106.0, 116.0, 101.0, 115.0),  # most recent
            ]
        if barSizeSetting == '1 hour':
            n = 120 if durationStr in ('120 H', '3 D') else 60
            base = 100.0
            return [self._Bar(base + i * 0.1, base + i * 0.1, base + i * 0.1, base + i * 0.1) for i in range(n)]
        return []


class MockPosition:
    def __init__(self, contract, position):
        self.contract = contract
        self.position = position
