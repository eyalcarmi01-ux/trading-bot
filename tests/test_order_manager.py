import unittest
import math
from unittest.mock import MagicMock, patch
from order_manager import (
    place_bracket_orders, 
    contracts_match, 
    order_filled, 
    get_market_price,
    cancel_all_orders,
    close_all_positions
)

class MockContract:
    def __init__(self, symbol="CL", secType="FUT", exchange="NYMEX", currency="USD", month="202601"):
        self.symbol = symbol
        self.secType = secType
        self.exchange = exchange
        self.currency = currency
        self.lastTradeDateOrContractMonth = month
        self.conId = 12345

class MockOrder:
    def __init__(self, orderId=1, orderType="MKT", action="BUY", totalQuantity=1):
        self.orderId = orderId
        self.orderType = orderType
        self.action = action
        self.totalQuantity = totalQuantity

class MockTrade:
    def __init__(self, orderId=1, status="Submitted"):
        self.order = MockOrder(orderId)
        self.orderStatus = MagicMock()
        self.orderStatus.status = status

class MockTick:
    def __init__(self, last=100, close=100, bid=99, ask=101):
        self.last = last
        self.close = close
        self.bid = bid
        self.ask = ask

class TestOrderManager(unittest.TestCase):
    def setUp(self):
        self.mock_ib = MagicMock()
        self.mock_contract = MockContract()
        self.mock_config = MagicMock()
        self.mock_config.sl_ticks = 10
        self.mock_config.tp_ticks_long = 20
        self.mock_config.tp_ticks_short = 15
        self.mock_config.tick_size = 0.01

    def test_place_bracket_orders_buy(self):
        self.mock_ib.reqMktData.return_value = MockTick()
        
        result = place_bracket_orders(
            self.mock_config, 
            self.mock_ib, 
            quantity=1, 
            action="BUY"
        )
        
        self.assertTrue(result)
        # Should place 3 orders (entry, SL, TP)
        self.assertEqual(self.mock_ib.placeOrder.call_count, 3)

    def test_place_bracket_orders_sell(self):
        self.mock_ib.reqMktData.return_value = MockTick()
        
        result = place_bracket_orders(
            self.mock_config, 
            self.mock_ib, 
            quantity=1, 
            action="SELL"
        )
        
        self.assertTrue(result)
        self.assertEqual(self.mock_ib.placeOrder.call_count, 3)

    def test_place_bracket_orders_invalid_action(self):
        self.mock_ib.reqMktData.return_value = MockTick()
        
        result = place_bracket_orders(
            self.mock_config, 
            self.mock_ib, 
            quantity=1, 
            action="INVALID"
        )
        
        self.assertFalse(result)
        self.assertEqual(self.mock_ib.placeOrder.call_count, 0)

    def test_place_bracket_orders_invalid_price(self):
        self.mock_ib.reqMktData.return_value = MockTick(last=None, close=None, bid=None, ask=None)
        
        result = place_bracket_orders(
            self.mock_config, 
            self.mock_ib, 
            quantity=1, 
            action="BUY"
        )
        
        self.assertFalse(result)
        self.assertEqual(self.mock_ib.placeOrder.call_count, 0)

    def test_place_bracket_orders_zero_quantity(self):
        self.mock_ib.reqMktData.return_value = MockTick()
        
        result = place_bracket_orders(
            self.mock_config, 
            self.mock_ib, 
            quantity=0, 
            action="BUY"
        )
        
        self.assertFalse(result)

    def test_place_bracket_orders_negative_quantity(self):
        self.mock_ib.reqMktData.return_value = MockTick()
        
        result = place_bracket_orders(
            self.mock_config, 
            self.mock_ib, 
            quantity=-1, 
            action="BUY"
        )
        
        self.assertFalse(result)

    def test_contracts_match_identical(self):
        contract1 = MockContract()
        contract2 = MockContract()
        
        self.assertTrue(contracts_match(contract1, contract2))

    def test_contracts_match_different_symbol(self):
        contract1 = MockContract(symbol="CL")
        contract2 = MockContract(symbol="ES")
        
        self.assertFalse(contracts_match(contract1, contract2))

    def test_contracts_match_different_exchange(self):
        contract1 = MockContract(exchange="NYMEX")
        contract2 = MockContract(exchange="CME")
        
        self.assertFalse(contracts_match(contract1, contract2))

    def test_contracts_match_different_month(self):
        contract1 = MockContract(month="202601")
        contract2 = MockContract(month="202602")
        
        self.assertFalse(contracts_match(contract1, contract2))

    def test_order_filled_true(self):
        trade = MockTrade(orderId=123, status="Filled")
        self.mock_ib.trades.return_value = [trade]
        
        result = order_filled(self.mock_ib, 123)
        
        self.assertTrue(result)

    def test_order_filled_false(self):
        trade = MockTrade(orderId=123, status="Submitted")
        self.mock_ib.trades.return_value = [trade]
        
        result = order_filled(self.mock_ib, 123)
        
        self.assertFalse(result)

    def test_order_filled_not_found(self):
        trade = MockTrade(orderId=456, status="Filled")
        self.mock_ib.trades.return_value = [trade]
        
        result = order_filled(self.mock_ib, 123)
        
        self.assertFalse(result)

    def test_get_market_price_all_valid(self):
        tick = MockTick(last=100, close=99, bid=98, ask=102)
        
        price = get_market_price(tick)
        
        self.assertEqual(price, 99.75)  # Average of all prices

    def test_get_market_price_some_invalid(self):
        tick = MockTick(last=100, close=math.nan, bid=98, ask=None)
        
        price = get_market_price(tick)
        
        self.assertEqual(price, 99.0)  # Average of valid prices only

    def test_get_market_price_all_invalid(self):
        tick = MockTick(last=None, close=math.nan, bid=math.inf, ask=None)
        
        price = get_market_price(tick)
        
        self.assertIsNone(price)

    def test_cancel_all_orders(self):
        mock_orders = [MockOrder(1), MockOrder(2), MockOrder(3)]
        self.mock_ib.orders.return_value = mock_orders
        
        cancel_all_orders(self.mock_ib)
        
        self.assertEqual(self.mock_ib.cancelOrder.call_count, 3)

    def test_cancel_all_orders_empty(self):
        self.mock_ib.orders.return_value = []
        
        cancel_all_orders(self.mock_ib)
        
        self.assertEqual(self.mock_ib.cancelOrder.call_count, 0)

    def test_close_all_positions(self):
        mock_position = MagicMock()
        mock_position.position = 2
        mock_position.contract = self.mock_contract
        self.mock_ib.positions.return_value = [mock_position]
        
        close_all_positions(self.mock_ib)
        
        self.mock_ib.placeOrder.assert_called_once()

    def test_close_all_positions_zero_position(self):
        mock_position = MagicMock()
        mock_position.position = 0
        mock_position.contract = self.mock_contract
        self.mock_ib.positions.return_value = [mock_position]
        
        close_all_positions(self.mock_ib)
        
        self.mock_ib.placeOrder.assert_not_called()

    def test_place_bracket_orders_with_exception(self):
        self.mock_ib.reqMktData.side_effect = Exception("Network error")
        
        result = place_bracket_orders(
            self.mock_config, 
            self.mock_ib, 
            quantity=1, 
            action="BUY"
        )
        
        self.assertFalse(result)

    @patch('order_manager.logger')
    def test_place_bracket_orders_logs_success(self, mock_logger):
        self.mock_ib.reqMktData.return_value = MockTick()
        
        place_bracket_orders(
            self.mock_config, 
            self.mock_ib, 
            quantity=1, 
            action="BUY"
        )
        
        mock_logger.info.assert_called()

    @patch('order_manager.logger')
    def test_get_market_price_logs_warning(self, mock_logger):
        tick = MockTick(last=None, close=None, bid=None, ask=None)
        
        get_market_price(tick)
        
        mock_logger.warning.assert_called_with("⚠️ No valid market price found in tick data.")

if __name__ == '__main__':
    unittest.main()
