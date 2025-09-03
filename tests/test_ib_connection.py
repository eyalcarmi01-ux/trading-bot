import unittest
from unittest.mock import MagicMock, patch
from ib_connection import connect_ib, reconnect_ib, disconnect_ib, is_connected

class TestIBConnection(unittest.TestCase):
    def setUp(self):
        self.mock_ib = MagicMock()
        self.mock_config = MagicMock()
        self.mock_config.ib_host = "127.0.0.1"
        self.mock_config.ib_port = 7497
        self.mock_config.client_id = 1

    @patch('ib_connection.IB')
    def test_connect_ib_success(self, mock_ib_class):
        mock_ib_class.return_value = self.mock_ib
        self.mock_ib.connect.return_value = None
        self.mock_ib.isConnected.return_value = True
        
        ib = connect_ib(self.mock_config)
        
        self.assertIsNotNone(ib)
        self.mock_ib.connect.assert_called_once_with(
            "127.0.0.1", 7497, clientId=1
        )

    @patch('ib_connection.IB')
    def test_connect_ib_failure(self, mock_ib_class):
        mock_ib_class.return_value = self.mock_ib
        self.mock_ib.connect.side_effect = Exception("Connection failed")
        
        with self.assertRaises(Exception):
            connect_ib(self.mock_config)

    @patch('ib_connection.IB')
    def test_connect_ib_timeout(self, mock_ib_class):
        mock_ib_class.return_value = self.mock_ib
        self.mock_ib.connect.side_effect = TimeoutError("Connection timeout")
        
        with self.assertRaises(TimeoutError):
            connect_ib(self.mock_config)

    def test_reconnect_ib_success(self):
        self.mock_ib.isConnected.return_value = False
        self.mock_ib.connect.return_value = None
        
        result = reconnect_ib(self.mock_ib, self.mock_config)
        
        self.assertTrue(result)
        self.mock_ib.disconnect.assert_called_once()
        self.mock_ib.connect.assert_called_once()

    def test_reconnect_ib_already_connected(self):
        self.mock_ib.isConnected.return_value = True
        
        result = reconnect_ib(self.mock_ib, self.mock_config)
        
        self.assertTrue(result)
        self.mock_ib.disconnect.assert_not_called()
        self.mock_ib.connect.assert_not_called()

    def test_reconnect_ib_failure(self):
        self.mock_ib.isConnected.return_value = False
        self.mock_ib.connect.side_effect = Exception("Reconnection failed")
        
        result = reconnect_ib(self.mock_ib, self.mock_config)
        
        self.assertFalse(result)

    def test_disconnect_ib_success(self):
        self.mock_ib.isConnected.return_value = True
        
        disconnect_ib(self.mock_ib)
        
        self.mock_ib.disconnect.assert_called_once()

    def test_disconnect_ib_not_connected(self):
        self.mock_ib.isConnected.return_value = False
        
        disconnect_ib(self.mock_ib)
        
        self.mock_ib.disconnect.assert_not_called()

    def test_disconnect_ib_with_exception(self):
        self.mock_ib.isConnected.return_value = True
        self.mock_ib.disconnect.side_effect = Exception("Disconnect error")
        
        # Should not raise exception
        disconnect_ib(self.mock_ib)
        
        self.mock_ib.disconnect.assert_called_once()

    def test_is_connected_true(self):
        self.mock_ib.isConnected.return_value = True
        
        result = is_connected(self.mock_ib)
        
        self.assertTrue(result)

    def test_is_connected_false(self):
        self.mock_ib.isConnected.return_value = False
        
        result = is_connected(self.mock_ib)
        
        self.assertFalse(result)

    def test_is_connected_with_exception(self):
        self.mock_ib.isConnected.side_effect = Exception("Connection check error")
        
        result = is_connected(self.mock_ib)
        
        self.assertFalse(result)

    @patch('ib_connection.time.sleep')
    def test_connect_with_retry(self, mock_sleep):
        with patch('ib_connection.IB') as mock_ib_class:
            mock_ib_class.return_value = self.mock_ib
            # First attempt fails, second succeeds
            self.mock_ib.connect.side_effect = [Exception("First fail"), None]
            self.mock_ib.isConnected.return_value = True
            
            ib = connect_ib(self.mock_config, max_retries=2)
            
            self.assertIsNotNone(ib)
            self.assertEqual(self.mock_ib.connect.call_count, 2)

    @patch('ib_connection.time.sleep')
    def test_connect_max_retries_exceeded(self, mock_sleep):
        with patch('ib_connection.IB') as mock_ib_class:
            mock_ib_class.return_value = self.mock_ib
            self.mock_ib.connect.side_effect = Exception("Always fails")
            
            with self.assertRaises(Exception):
                connect_ib(self.mock_config, max_retries=3)
            
            self.assertEqual(self.mock_ib.connect.call_count, 3)

    @patch('ib_connection.logger')
    def test_connect_logs_success(self, mock_logger):
        with patch('ib_connection.IB') as mock_ib_class:
            mock_ib_class.return_value = self.mock_ib
            self.mock_ib.connect.return_value = None
            self.mock_ib.isConnected.return_value = True
            
            connect_ib(self.mock_config)
            
            mock_logger.info.assert_called()

    @patch('ib_connection.logger')
    def test_connect_logs_failure(self, mock_logger):
        with patch('ib_connection.IB') as mock_ib_class:
            mock_ib_class.return_value = self.mock_ib
            self.mock_ib.connect.side_effect = Exception("Connection failed")
            
            with self.assertRaises(Exception):
                connect_ib(self.mock_config)
            
            mock_logger.error.assert_called()

    def test_connect_with_different_client_ids(self):
        with patch('ib_connection.IB') as mock_ib_class:
            mock_ib_class.return_value = self.mock_ib
            self.mock_ib.connect.return_value = None
            self.mock_ib.isConnected.return_value = True
            
            # Test with different client IDs
            for client_id in [1, 10, 99]:
                self.mock_config.client_id = client_id
                ib = connect_ib(self.mock_config)
                self.assertIsNotNone(ib)

    def test_connect_with_invalid_host(self):
        with patch('ib_connection.IB') as mock_ib_class:
            mock_ib_class.return_value = self.mock_ib
            self.mock_ib.connect.side_effect = Exception("Invalid host")
            self.mock_config.ib_host = "invalid_host"
            
            with self.assertRaises(Exception):
                connect_ib(self.mock_config)

    def test_connect_with_invalid_port(self):
        with patch('ib_connection.IB') as mock_ib_class:
            mock_ib_class.return_value = self.mock_ib
            self.mock_ib.connect.side_effect = Exception("Invalid port")
            self.mock_config.ib_port = -1
            
            with self.assertRaises(Exception):
                connect_ib(self.mock_config)

if __name__ == '__main__':
    unittest.main()
