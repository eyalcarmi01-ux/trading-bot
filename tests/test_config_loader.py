import unittest
import json
import tempfile
import os
from unittest.mock import patch, mock_open
from config_loader import load_config, validate_config

class TestConfigLoader(unittest.TestCase):
    def setUp(self):
        self.valid_config = {
            "symbol": "CL",
            "exchange": "NYMEX",
            "currency": "USD",
            "contract_month": "202601",
            "ib_host": "127.0.0.1",
            "ib_port": 7497,
            "client_id": 1,
            "check_interval": 60,
            "quantity": 1,
            "strategy_module": "strategy.CCI14_200signal",
            "trade_start": {"hour": 8, "minute": 0},
            "trade_end": {"hour": 22, "minute": 30}
        }

    def test_load_valid_config(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(self.valid_config, f)
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            self.assertEqual(config.symbol, "CL")
            self.assertEqual(config.ib_port, 7497)
        finally:
            os.unlink(temp_path)

    def test_load_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write('{"invalid": json}')
            temp_path = f.name
        
        try:
            with self.assertRaises(json.JSONDecodeError):
                load_config(temp_path)
        finally:
            os.unlink(temp_path)

    def test_missing_config_file(self):
        with self.assertRaises(FileNotFoundError):
            load_config("nonexistent_config.json")

    def test_missing_required_keys(self):
        incomplete_config = self.valid_config.copy()
        del incomplete_config['symbol']
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(incomplete_config, f)
            temp_path = f.name
        
        try:
            with self.assertRaises(KeyError):
                config = load_config(temp_path)
                validate_config(config)
        finally:
            os.unlink(temp_path)

    def test_invalid_port_type(self):
        invalid_config = self.valid_config.copy()
        invalid_config['ib_port'] = "not_a_number"
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(invalid_config, f)
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            with self.assertRaises((TypeError, ValueError)):
                validate_config(config)
        finally:
            os.unlink(temp_path)

    def test_negative_values(self):
        invalid_config = self.valid_config.copy()
        invalid_config['quantity'] = -1
        invalid_config['check_interval'] = -60
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(invalid_config, f)
            temp_path = f.name
        
        try:
            config = load_config(temp_path)
            with self.assertRaises(ValueError):
                validate_config(config)
        finally:
            os.unlink(temp_path)

    def test_empty_config_file(self):
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write('')
            temp_path = f.name
        
        try:
            with self.assertRaises(json.JSONDecodeError):
                load_config(temp_path)
        finally:
            os.unlink(temp_path)

if __name__ == '__main__':
    unittest.main()
