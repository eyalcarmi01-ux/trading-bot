# Trading Bot (algorithms + tests)

Minimal refactor of trading algorithms with a focused test suite.

## What’s here
- algorithms/
  - trading_algorithms_class.py — Base class with IB integration helpers
  - ema_trading_algorithm.py — EMA-based strategy
  - cci14_compare_trading_algorithm.py — CCI(14) compare / delayed bracket strategy (waits N minutes after signal)
  - cci14_120_trading_algorithm.py — CCI(14) reversal strategy (±120 threshold, delayed bracket phase logic)
  - cci14_200_trading_algorithm.py — CCI(14) immediate threshold breakout strategy (±200, intraday time window)
  - fibonacci_trading_algorithm.py — Fibonacci retracement strategy
- tests/ — Curated unittest suite covering base behavior, signals, state, regression, and perf sanity checks
- .github/workflows/ci.yml — CI to run the test suite on push/PR
- requirements.txt — Minimal runtime deps (ib-insync)

### Trade lifecycle state machine
The base class now tracks a normalized trade lifecycle via `trade_phase`:

`IDLE -> SIGNAL_PENDING -> BRACKET_SENT -> ACTIVE -> EXITING -> CLOSED -> IDLE`

Transitions are logged with a single line, e.g.:
```
🔄 PHASE SIGNAL_PENDING -> BRACKET_SENT (Sending bracket order) | 0.11s in prev phase
```
Key meanings:
- IDLE: No active trade or pending signal.
- SIGNAL_PENDING: Strategy detected a qualified signal and is in any mandated delay window.
- BRACKET_SENT: Bracket order just submitted (may advance quickly to ACTIVE once transmitted).
- ACTIVE: Position open; monitoring TP/SL or strategy-specific exit conditions.
- EXITING: Manual intervention (e.g. proactive SL breach) underway.
- CLOSED: Terminal state immediately after TP/SL/manual close fill; automatically resets to IDLE.

### Unified logging
- One rotating (append-mode) log file per algorithm class in `logs/` (e.g. `CCI14_Compare_TradingAlgorithm.log`, `CCI14_200_TradingAlgorithm.log`).
- Each line includes timestamp + client id + message.
- Method calls auto-traced via a metaclass (lines prefixed with `CALL Class.method()`).

Legacy names (e.g. `CCI14TradingAlgorithm`, `CCI14ThresholdTradingAlgorithm`) were removed in favor of explicit variants (`CCI14_Compare_...`, `CCI14_200_...`) for clarity.

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

You can run a specific lifecycle test:
```
python -m unittest tests.test_lifecycle.TestLifecyclePhases.test_bracket_order_phase_sequence -v
```

Test discovery is intentionally scoped in `tests/__init__.py` to only run algorithm-related tests.

## Notes
- Algorithms expect an Interactive Brokers connection (IB Gateway/TWS) in production.
- Tests use lightweight mock IB objects to avoid network calls.
- Only code in `algorithms/` (and the base class) is considered in scope here.
 - Lifecycle and logging behavior covered by `tests/test_lifecycle.py`.
 - Current curated suite: 63 tests (signal logic, lifecycle phases, bracket tracking, performance sanity, regression paths).

## CI
GitHub Actions workflow runs the same unittest command on every push/PR against `main`.
