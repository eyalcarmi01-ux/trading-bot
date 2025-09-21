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
  - Multi-span EMA diagnostics & bootstrap (CCI variants) and EMA extended diagnostics
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
 - Current curated suite: 76 tests (signal logic, lifecycle phases, bracket tracking, performance sanity, regression paths).

### Internal method naming (encapsulation refactor)
Several lifecycle/housekeeping helpers were converted from public to internal (underscore) methods to clarify the supported public surface of `TradingAlgorithm`:

| Old public name                | New internal name            | Purpose (unchanged)                                  |
|--------------------------------|------------------------------|------------------------------------------------------|
| perform_startup_test_order     | _perform_startup_test_order  | Optional connectivity sanity test order              |
| monitor_stop                   | _monitor_stop                | Manual SL breach detection & forced flat logic       |
| check_fills_and_reset_state    | _check_fills_and_reset_state | Scan trades for TP/SL fills and reset trade state    |
| wait_for_round_minute          | _wait_for_round_minute       | Align initial start to next round minute             |
| handle_active_position         | _handle_active_position      | Active position monitoring + phase management        |

Public extension points remain:
- run()
- on_tick(time_str)
- pre_run()
- place_bracket_order(...)
- has_active_position()
- get_valid_price(), update_price_history(), calculate_ema()

### Daily force-close (new)
All algorithms now support an optional `force_close=(hour, minute)` argument passed into the base `TradingAlgorithm` constructor (and therefore any subclass). When configured:

- At or after the specified intraday wall-clock time (in the algorithm's `trade_timezone`), any open position is flattened (market order) and all outstanding orders are cancelled.
- The lifecycle transitions `... -> CLOSED -> IDLE` (reset) and the algorithm continues running (it does NOT terminate the loop; that remains governed by the `shutdown_at` window).
- The force-close timestamp automatically rolls forward to the next trading day after triggering.

Usage example (21:45 daily flatten):
```python
algo = CCI14_200_TradingAlgorithm(
  contract_params=contract,
  check_interval=60,
  initial_ema=80,
  force_close=(21, 45),
  shutdown_at=(22, 50),
)
```

Launcher default:
The provided multi-algorithm launcher `main_class.py` currently applies a uniform
`force_close=(22, 50)` to every instantiated algorithm (see `FORCE_CLOSE_TIME` constant).
Adjust that constant (or pass a per‑algo value in the constructors) if you need a
different daily flatten time. No CLI flag is required or parsed for this.

Ordering of intraday controls each loop:
1. Force-close check (flatten only, keeps running)
2. Pause window (pre-market) skip
3. New-order cutoff (blocks fresh brackets, existing positions still monitored)
4. Shutdown window (final cancel + flatten + loop exit)

If both `force_close` and `shutdown_at` would occur in the same minute, force-close runs first; shutdown then exits on the next iteration.

Tests were updated to reference the new internal names where direct invocation was required for deterministic verification (e.g. timing or fill scanning). External callers / strategy authors should treat underscored methods as implementation details subject to change.

### Multi-span EMA diagnostics (CCI strategies)
`CCI14_Compare_TradingAlgorithm` (and thus `CCI14_200_TradingAlgorithm` via inheritance when its own override path isn't used) supports optional multi-span EMA tracking:

- Spans default: `(10, 20, 32, 50, 100, 200)`
- Enabled by default (`multi_ema_diagnostics=True` in launcher)
- Periodic line example:

```
12:00:00 🧪 EMAS: EMA10=80.12 | EMA20=80.05 | EMA32=79.98 | EMA50=79.90 | EMA100=79.75 | EMA200=79.10
```

Historical bootstrap (when connected live and not under test):
- Fetches 1‑minute bars (`~2 D` lookback) to seed each EMA span once
- Falls back silently if unavailable or in mock/test context

Constructor flags:
```
CCI14_Compare_TradingAlgorithm(
  ...,
  multi_ema_diagnostics=True,
  ema_spans=(10,20,32,50,100,200),
  multi_ema_bootstrap=True,
  bootstrap_lookback_bars=300,
)
```

### Extended EMA diagnostics (EMA strategy)
`EMATradingAlgorithm` exposes lightweight performance / slope diagnostics (disabled by default in launcher to avoid noisy logs in multi‑strategy setups):

- `diagnostics_enabled` (bool) and `diagnostics_every` (int tick interval)
- Captures EMA slope, price latency timing, and a compact JSON blob for external parsing.

### Classic vs stdev CCI toggle
CCI(14) can be computed two ways:

1. Current (default for compare/120 variants): sample standard deviation denominator.
2. Classic (mean deviation) formula: `(TP - avg(TP)) / (0.015 * meanDeviation)` — historically common in literature.

Implementation:
- `classic_cci=False` (default) uses stdev.
- `classic_cci=True` switches to mean deviation.
- The 200-threshold variant (`CCI14_200_TradingAlgorithm`) is configured in `main_class.py` with `classic_cci=True` by default for legacy parity comparison.

Log output examples:
```
12:00:00 📊 CCI14(stdev): 132.5 | Prev: 129.3 🔼 | Mean: 82.11 | StdDev: 1.23
12:00:00 📊 CCI14(classic): 140.7 | Prev: 138.9 🔼 | Mean: 82.11 | MeanDev: 0.87
```

Unit tests now assert numerical parity for both calculation modes (see `tests/test_cci14_200_trading_algorithm.py`).

## CI
GitHub Actions workflow runs the same unittest command on every push/PR against `main`.

## Coverage
Install dev dependency (already listed in requirements):

```
pip install -r requirements.txt
```

Generate terminal + HTML coverage (source limited to `algorithms/` via `.coveragerc`):

```
coverage run -m unittest discover -v && coverage report -m && coverage html
```

Open `coverage_html/index.html` in a browser for annotated source.

Notes:
- Branch coverage enabled.
- Tests and package `__init__` files are omitted.
- Missing lines are shown in summary; aim to keep critical lifecycle paths covered.
