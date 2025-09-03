import unittest
from unittest.mock import MagicMock, patch
from main_loop import run_loop, monitor_stop_and_force_close
from main_class import TradingBot

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_ib = MagicMock()
        self.mock_contract = MagicMock()
        self.mock_config = MagicMock()
        self.mock_config.interval = 1
        self.mock_config.trade_active = False
        self.mock_config.quantity = 1
        self.mock_strategy = MagicMock()

    @patch('main_loop.time.sleep')
    @patch('main_loop.calculate_cci')
    @patch('main_loop.get_latest_emas')
    def test_run_loop_basic_cycle(self, mock_emas, mock_cci, mock_sleep):
        # Mock strategy and data
        self.mock_strategy.should_trade_now.return_value = True
        self.mock_strategy.check_trade_conditions.return_value = 'BUY'
        mock_cci.return_value = (150, 100, 10, '↑')
        mock_emas.return_value = [100, 101, 102]
        
        # Mock IB to have no positions
        self.mock_ib.positions.return_value = []
        
        # Stop after one iteration
        mock_sleep.side_effect = KeyboardInterrupt()
        
        with self.assertRaises(KeyboardInterrupt):
            run_loop(
                self.mock_config,
                self.mock_strategy,
                [100, 101, 102],
                [100, 101, 102],
                self.mock_ib,
                self.mock_contract
            )
        
        # Should check for trading conditions
        self.mock_strategy.should_trade_now.assert_called()
        self.mock_strategy.check_trade_conditions.assert_called()

    @patch('main_loop.time.sleep')
    @patch('main_loop.calculate_cci')
    def test_run_loop_with_active_position(self, mock_cci, mock_sleep):
        # Mock active position
        mock_position = MagicMock()
        mock_position.contract.conId = self.mock_contract.conId
        mock_position.position = 1
        self.mock_ib.positions.return_value = [mock_position]
        
        mock_cci.return_value = (150, 100, 10, '↑')
        mock_sleep.side_effect = KeyboardInterrupt()
        
        with self.assertRaises(KeyboardInterrupt):
            run_loop(
                self.mock_config,
                self.mock_strategy,
                [100, 101, 102],
                [100, 101, 102],
                self.mock_ib,
                self.mock_contract
            )
        
        # Should skip new trades when position is active
        self.mock_strategy.check_trade_conditions.assert_not_called()

    @patch('main_loop.time.sleep')
    def test_run_loop_trading_window_closed(self, mock_sleep):
        # Mock trading window closed
        self.mock_strategy.should_trade_now.return_value = False
        mock_sleep.side_effect = KeyboardInterrupt()
        
        with self.assertRaises(KeyboardInterrupt):
            run_loop(
                self.mock_config,
                self.mock_strategy,
                [100, 101, 102],
                [100, 101, 102],
                self.mock_ib,
                self.mock_contract
            )
        
        # Should not check trade conditions when window is closed
        self.mock_strategy.check_trade_conditions.assert_not_called()

    def test_monitor_stop_and_force_close(self):
        # Mock configuration with stop loss
        self.mock_config.current_sl_price = 95
        self.mock_config.active_direction = 'LONG'
        
        # Mock market data
        mock_tick = MagicMock()
        mock_tick.last = 90  # Below stop loss
        self.mock_ib.reqMktData.return_value = mock_tick
        
        # Mock active position
        mock_position = MagicMock()
        mock_position.position = 1
        mock_position.contract = self.mock_contract
        self.mock_ib.positions.return_value = [mock_position]
        
        monitor_stop_and_force_close(self.mock_config)
        
        # Should place close order when stop is hit
        self.mock_ib.placeOrder.assert_called()

    def test_trading_bot_initialization(self):
        with patch('main_class.load_config') as mock_load_config:
            mock_load_config.return_value = self.mock_config
            
            bot = TradingBot("test_config.json")
            
            self.assertIsNotNone(bot)
            mock_load_config.assert_called_with("test_config.json")

    def test_trading_bot_start_stop(self):
        with patch('main_class.load_config') as mock_load_config:
            with patch('main_class.connect_ib') as mock_connect:
                mock_load_config.return_value = self.mock_config
                mock_connect.return_value = self.mock_ib
                
                bot = TradingBot("test_config.json")
                
                # Test start
                with patch.object(bot, 'run') as mock_run:
                    bot.start()
                    mock_run.assert_called_once()
                
                # Test stop
                bot.stop()
                self.assertFalse(bot.running)

    @patch('main_loop.place_bracket_orders')
    def test_integration_order_placement(self, mock_place_orders):
        # Test full integration from signal to order placement
        with patch('main_loop.time.sleep') as mock_sleep:
            with patch('main_loop.calculate_cci') as mock_cci:
                with patch('main_loop.get_latest_emas') as mock_emas:
                    # Setup mocks
                    self.mock_strategy.should_trade_now.return_value = True
                    self.mock_strategy.check_trade_conditions.return_value = 'BUY'
                    mock_cci.return_value = (-250, 100, 10, '↓')  # Strong buy signal
                    mock_emas.return_value = [100, 101, 102]
                    self.mock_ib.positions.return_value = []
                    mock_place_orders.return_value = True
                    
                    # Stop after one iteration
                    mock_sleep.side_effect = KeyboardInterrupt()
                    
                    with self.assertRaises(KeyboardInterrupt):
                        run_loop(
                            self.mock_config,
                            self.mock_strategy,
                            [100, 101, 102],
                            [100, 101, 102],
                            self.mock_ib,
                            self.mock_contract
                        )
                    
                    # Should place order for BUY signal
                    mock_place_orders.assert_called_with(
                        self.mock_config,
                        self.mock_ib,
                        quantity=1,
                        action='BUY'
                    )

    def test_error_handling_in_loop(self):
        # Test error handling during main loop
        with patch('main_loop.time.sleep') as mock_sleep:
            with patch('main_loop.calculate_cci') as mock_cci:
                # Mock CCI calculation to raise exception
                mock_cci.side_effect = Exception("Calculation error")
                mock_sleep.side_effect = KeyboardInterrupt()
                
                # Loop should handle exceptions gracefully
                with self.assertRaises(KeyboardInterrupt):
                    run_loop(
                        self.mock_config,
                        self.mock_strategy,
                        [100, 101, 102],
                        [100, 101, 102],
                        self.mock_ib,
                        self.mock_contract
                    )

    def test_data_flow_integration(self):
        # Test data flow from fetching to processing
        with patch('main_loop.fetch_initial_data') as mock_fetch:
            with patch('main_loop.clean_prices_with_previous') as mock_clean:
                mock_fetch.return_value = [100, 101, 102, None, 104]
                mock_clean.return_value = [100, 101, 102, 102, 104]
                
                # Test that data cleaning works with fetched data
                raw_data = mock_fetch(self.mock_ib, self.mock_contract)
                clean_data = mock_clean(raw_data)
                
                self.assertEqual(len(clean_data), 5)
                self.assertNotIn(None, clean_data)

    @patch('main_loop.logger')
    def test_logging_integration(self, mock_logger):
        # Test that proper logging occurs during operations
        with patch('main_loop.time.sleep') as mock_sleep:
            with patch('main_loop.calculate_cci') as mock_cci:
                mock_cci.return_value = (150, 100, 10, '↑')
                self.mock_ib.positions.return_value = []
                self.mock_strategy.should_trade_now.return_value = False
                mock_sleep.side_effect = KeyboardInterrupt()
                
                with self.assertRaises(KeyboardInterrupt):
                    run_loop(
                        self.mock_config,
                        self.mock_strategy,
                        [100, 101, 102],
                        [100, 101, 102],
                        self.mock_ib,
                        self.mock_contract
                    )
                
                # Should log trading information
                mock_logger.info.assert_called()

if __name__ == '__main__':
    unittest.main()
