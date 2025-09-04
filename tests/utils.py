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

    # --- IB-like methods used by tests/algorithms ---
    def connect(self, *a, **kw):
        self.connected = True

    def disconnect(self):
        self.connected = False

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


class MockPosition:
    def __init__(self, contract, position):
        self.contract = contract
        self.position = position
