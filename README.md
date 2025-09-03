# Trading Bot (algorithms + tests)

Minimal refactor of trading algorithms with a focused test suite.

## What’s here
- algorithms/
  - trading_algorithms_class.py — Base class with IB integration helpers
  - ema_trading_algorithm.py — EMA-based strategy
  - cci14_trading_algorithm.py — CCI(14) trend strategy
  - cci14rev_trading_algorithm.py — CCI(14) reversal strategy
  - fibonacci_trading_algorithm.py — Fibonacci retracement strategy
- tests/ — Curated unittest suite covering base behavior, signals, state, regression, and perf sanity checks
- .github/workflows/ci.yml — CI to run the test suite on push/PR
- requirements.txt — Minimal runtime deps (ib-insync)

## Requirements
- Python 3.11+
- ib-insync (see requirements.txt)

Install:

```
pip install -r requirements.txt
```

## Run tests

```
python -m unittest -v
```

Test discovery is intentionally scoped in `tests/__init__.py` to only run algorithm-related tests.

## Notes
- Algorithms expect an Interactive Brokers connection (IB Gateway/TWS) in production.
- Tests use lightweight mock IB objects to avoid network calls.
- Only code in `algorithms/` (and the base class) is considered in scope here.

## CI
GitHub Actions workflow runs the same unittest command on every push/PR against `main`.
