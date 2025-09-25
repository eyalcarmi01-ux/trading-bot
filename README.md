# Trading Bot

Modernized Python trading strategies with a shared base engine, unified seeding/gating, rich logging/CSV export, and a focused unit test suite.

## Quick start

Requirements
- Python 3.11+
- ib-insync (see requirements.txt)

Install deps

```
pip install -r requirements.txt
```

Run tests

```
python -m unittest -v
```

Run the demo launcher (multiple algos, staggered threads)

```
python main_class.py
```

Notes
- Console output: By default only the CCI-200 algo prints to console; all algos log to files under `logs/`.
- Override console selection (comma-separated class names): `CONSOLE_ALGOS=CCI14_200_TradingAlgorithm,EMATradingAlgorithm`
- ES logging defaults (launcher): `TRADES_ES_ENABLED=1`, `TRADES_ES_INDEX=trades`, `TRADES_ES_SEED_INDEX=trades_seed`.
  - If Elasticsearch is already reachable at `ES_URL` (default `http://localhost:9200`), Docker Compose is skipped.
  - When composing locally, data persists across runs via the `esdata` named volume in `docker-compose.yml`.
  - Sample trade seeding now happens only if the index is empty (idempotent). Use `python scripts/seed_trades_es.py --force trades` to reseed.

## Centralized indicators and runtime behavior

This project now centralizes common trading logic in the base class `TradingAlgorithm` (`algorithms/trading_algorithms_class.py`). All algorithms use these shared capabilities:

- EMA updates: `update_emas(price)` updates single-EMA, fast/slow EMA, and multi-EMA spans as available on the algorithm instance. Diagnostics are logged uniformly.
- CCI(14): `compute_and_log_cci(time_str)` delegates to the base calculator and stores values; `calculate_and_log_cci(prices, time_str)` performs the actual computation and emits concise logs.
- Verbose price history: `update_price_history_verbose(...)` tracks saved prices and prints the recent series for visibility.
- Trading window gating: `should_trade_now(now)` is the single source of truth for all algos. Trading ends at 23:00 per CCI-200 behavior, and this is applied project-wide.
- Console logging allowlist: by default only the CCI‑200 algorithm logs to console; other strategies still write to their log files. Adjust the allowlist in the base class if you want to surface additional algos to stdout.

### Shared per-tick prologue (tick_prologue)
Use `TradingAlgorithm.tick_prologue(...)` to handle common per-tick work and return a small context dict.

What it does
- Enforces trading window and returns early when blocked
- Fetches and logs the price (and writes CSV)
- Optionally updates EMAs and logs diagnostics
- Optionally updates price history and computes/logs CCI
- Returns a dict: { "price": float|None, "cci": float|None }

Typical usage in `on_tick`
- `ctx = self.tick_prologue(time_str, update_ema=True, compute_cci=True, price_annotator=lambda: {"EMA10": self.ema_fast, "EMA200": self.ema_slow})`
- If `ctx["price"]` is None: return
- Proceed with strategy-specific logic using `ctx`

Seeding and observability improvements:

- Generic historical seeding pulls 500 one‑minute bars for all strategies and primes EMAs/CCI consistently.
- All seeded history and calculated indicators are logged and also exported to CSV under `logs/` for offline inspection.
- Startup seeding and any test order wiring no longer wait for a round minute.

Testing notes:

- Time-dependent tests should patch datetime in the base module (where `should_trade_now` and other helpers read the time) to avoid brittleness.
- The unit test suite exercises all strategies against the centralized logic; use the provided VS Code task “Run all unittests”.

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

### Console output selection (default: only CCI‑200)
- By default, only `CCI14_200_TradingAlgorithm` prints to the console; all algorithms always write to their log files under `logs/`.
- You can override which algos print by setting the environment variable `CONSOLE_ALGOS` to a comma-separated list of class names (e.g., `CCI14_200_TradingAlgorithm,EMATradingAlgorithm`).
- Both method-call traces (CALL …) and regular instance log lines respect this filter. Non-listed algos will still log to files.
- The launcher (`main_class.py`) applies this at startup by updating `TradingAlgorithm.CONSOLE_ALLOWED` and setting each instance’s `log_to_console` accordingly.

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
 - Current curated suite: 78 tests (signal logic, lifecycle phases, bracket tracking, performance sanity, regression paths).

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
- Fetches 500 1‑minute bars (seconds-based duration) to seed history and prime indicators
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

## Elasticsearch + Kibana (optional)

This repo includes a local Elasticsearch + Kibana stack via Docker Compose to index logs or analytical events.

Setup
- Install Docker Desktop (macOS)
- Copy `.env.example` to `.env` and edit if needed (defaults work for local compose)
- Start services:

```
docker compose up -d
```

Services
- Elasticsearch: http://localhost:9200
- Kibana: http://localhost:5601

Python client
- Install deps: `pip install -r requirements.txt` (includes `elasticsearch`)
- Bootstrap an index and a sample doc:

```
python scripts/bootstrap_es.py trading-bot-logs
```

Minimal usage in code
- Use `es_client.get_es_client()` to obtain a client.
- Call `ensure_index` once, then `index_doc` or `bulk_index` for ingestion.

Kibana Discover views with ordered columns
- Create the Data Views and import the saved Discover searches (ordered columns) automatically:

```
python scripts/setup_kibana_saved_search.py
```

- Then open Kibana → Discover and select "Trades Discover (Ordered)" for the trades index. Columns are ordered as:
  `timestamp, algo, symbol, contract.*, event, action, quantity, price, pnl, cci, emas.*, reason`.

- For seeding/priming observability, select "Seed/Priming Discover (Ordered)" for the separate seed index. Columns are ordered as:
  `timestamp, algo, symbol, contract.*, event, history, priming`.

Security notes
- The compose file runs Elasticsearch with security disabled for local use only. For a secured setup, enable xpack security, set credentials, and define `ES_USERNAME`/`ES_PASSWORD`.

### Persistence and bind‑mount option
- By default, `docker-compose.yml` uses a named volume `esdata` so indices persist across runs.
- To store ES data under a host folder (easy backup/cleanup), set `ESDATA_PATH` in `.env`, e.g. `ESDATA_PATH=./.esdata`.
  The compose file is wired to honor this env var.

### Troubleshooting
- Docker not installed or not running: the launcher skips bootstrap and continues. Set `TRADES_ES_ENABLED=0` to silence ES logging attempts.
- ES already running locally (different compose or external): launcher detects and skips `docker compose up`.
- Port in use (9200/5601): change ports in `docker-compose.yml` or stop the other services.
- Re-seed sample docs: `python scripts/seed_trades_es.py --force trades` (default seeding only runs if the index is empty).
- Disable bootstrap explicitly: run `python main_class.py --no-bootstrap-es` or set `BOOTSTRAP_ES=0`.

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
