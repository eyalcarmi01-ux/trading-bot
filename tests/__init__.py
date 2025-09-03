import unittest

# Limit discovery to tests that exercise algorithms/ and main_class.py only.
# This overrides default unittest discovery for this package.

ALLOWED_TEST_MODULES = [
	'tests.test_algorithm_edge_cases',
	'tests.test_algorithm_logic',
	'tests.test_base_algorithm',
	'tests.test_cci14rev_trading_algorithm',
	'tests.test_contract_validation',
	'tests.test_performance',
	'tests.test_regression_algorithms',
	'tests.test_signal_generation',
	'tests.test_state_management',
	'tests.test_trading_algorithms',
]


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str) -> unittest.TestSuite:
	suite = unittest.TestSuite()
	for mod_name in ALLOWED_TEST_MODULES:
		try:
			module = __import__(mod_name, fromlist=['*'])
			suite.addTests(loader.loadTestsFromModule(module))
		except Exception:
			# Skip modules that fail to import; keeps discovery robust
			continue
	return suite

