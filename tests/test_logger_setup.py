import unittest
import tempfile
import os
import logging
from unittest.mock import patch, MagicMock
from logger_setup import setup_logger, get_logger

class TestLoggerSetup(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, 'test.log')

    def tearDown(self):
        # Clean up temp files
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)
        os.rmdir(self.temp_dir)

    def test_setup_logger_basic(self):
        logger = setup_logger('test_logger', self.log_file)
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, 'test_logger')

    def test_setup_logger_with_level(self):
        logger = setup_logger('test_logger', self.log_file, level=logging.WARNING)
        self.assertEqual(logger.level, logging.WARNING)

    def test_logger_file_creation(self):
        logger = setup_logger('test_logger', self.log_file)
        logger.info("Test message")
        self.assertTrue(os.path.exists(self.log_file))

    def test_logger_writes_to_file(self):
        logger = setup_logger('test_logger', self.log_file)
        test_message = "Test log message"
        logger.info(test_message)
        
        with open(self.log_file, 'r') as f:
            log_content = f.read()
            self.assertIn(test_message, log_content)

    def test_logger_multiple_handlers(self):
        logger = setup_logger('test_logger', self.log_file)
        initial_handlers = len(logger.handlers)
        
        # Adding same logger again shouldn't duplicate handlers
        logger2 = setup_logger('test_logger', self.log_file)
        self.assertEqual(len(logger2.handlers), initial_handlers)

    def test_get_logger(self):
        # Setup a logger first
        setup_logger('test_logger', self.log_file)
        retrieved_logger = get_logger('test_logger')
        self.assertIsInstance(retrieved_logger, logging.Logger)
        self.assertEqual(retrieved_logger.name, 'test_logger')

    def test_invalid_log_directory(self):
        invalid_path = "/invalid/directory/test.log"
        with self.assertRaises((FileNotFoundError, PermissionError, OSError)):
            logger = setup_logger('test_logger', invalid_path)
            logger.info("This should fail")

    def test_logger_formatting(self):
        logger = setup_logger('test_logger', self.log_file)
        logger.info("Test message")
        
        with open(self.log_file, 'r') as f:
            log_content = f.read()
            # Check that timestamp and level are included
            self.assertRegex(log_content, r'\d{4}-\d{2}-\d{2}')
            self.assertIn('INFO', log_content)

    def test_logger_different_levels(self):
        logger = setup_logger('test_logger', self.log_file, level=logging.INFO)
        
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        with open(self.log_file, 'r') as f:
            log_content = f.read()
            # Debug should not appear (below INFO level)
            self.assertNotIn("Debug message", log_content)
            self.assertIn("Info message", log_content)
            self.assertIn("Warning message", log_content)
            self.assertIn("Error message", log_content)

if __name__ == '__main__':
    unittest.main()
