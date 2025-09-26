import unittest
from unittest.mock import MagicMock, patch
import datetime

from algorithms.trading_algorithms_class import TradingAlgorithm

class TestBracketOrderRetriesAndStatus(unittest.TestCase):
    def setUp(self):
        contract_params = {
            'symbol': 'ES',
            'exchange': 'GLOBEX',
            'currency': 'USD',
            'secType': 'FUT',
            'lastTradeDateOrContractMonth': '202512'
        }
        self.mock_ib = MagicMock()
        # Mock contract with required attributes
        mock_contract = MagicMock()
        mock_contract.conId = 1
        self.mock_ib.qualifyContracts.return_value = [mock_contract]
        self.mock_ib.reqMktData.return_value = MagicMock(last=100.0, close=100.0, ask=100.0, bid=100.0)
        with patch('algorithms.trading_algorithms_class.Future', MagicMock(return_value=mock_contract)):
            self.algo = TradingAlgorithm(contract_params, ib=self.mock_ib)
        self.algo.contract = mock_contract
        self.algo._es_client = MagicMock()
        self.algo._es_trades_index = 'trades-test'
        self.algo._collect_contract_for_es = MagicMock(return_value={'symbol': 'ES'})
        self.algo.entry_ref_price = 100.0
        self.algo.entry_action = 'BUY'
        self.algo.entry_qty_sign = 1
        self.algo.current_sl_price = 95.0
        self.algo.trade_phase = 'IDLE'

    def test_retry_mechanism(self):
        # Simulate IB never confirming order status, count placeOrder calls
        self.algo.ib.trades.return_value = []
        self.algo.ib.placeOrder = MagicMock()
        self.algo.ib.cancelOrder = MagicMock()
        # Patch sleep to avoid delays
        with patch.object(self.algo.ib, 'sleep', return_value=None):
            self.algo.place_bracket_order('BUY', 1, 1.0, 5, 10, 10)
        # Should attempt to place bracket order 3 times
        self.assertGreaterEqual(self.algo.ib.placeOrder.call_count, 3)

    def test_order_status_polling(self):
        # Simulate IB confirming on 2nd attempt with correct orderId
        trade_mock = MagicMock()
        # Entry order mock with orderId matching what place_bracket_order will set
        entry_order_mock = MagicMock()
        entry_order_mock.orderId = 123
        # Patch placeOrder to set orderId on entry order
        def place_order_side_effect(contract, order):
            order.orderId = 123
            return order
        self.mock_ib.placeOrder.side_effect = place_order_side_effect
        trade_mock.order = entry_order_mock
        trade_mock.orderStatus = MagicMock(status='Submitted')
        self.mock_ib.trades.side_effect = [[], [], [trade_mock]]
        self.mock_ib.cancelOrder = MagicMock()
        with patch.object(self.mock_ib, 'sleep', return_value=None):
            self.algo.place_bracket_order('BUY', 1, 1.0, 5, 10, 10)
        self.assertEqual(self.algo.trade_phase, 'ACTIVE')

if __name__ == '__main__':
    unittest.main()
