import threading
import asyncio
import time
import random
import os
from algorithms.ema_trading_algorithm import EMATradingAlgorithm
from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm
from algorithms.cci14_compare_trading_algorithm import CCI14_Compare_TradingAlgorithm
from algorithms.cci14_120_trading_algorithm import CCI14_120_TradingAlgorithm
from algorithms.cci14_200_trading_algorithm import CCI14_200_TradingAlgorithm
from algorithms.trading_algorithms_class import TradingAlgorithm



# Example contract parameters (customize as needed for each algo)
ema_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
fib_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202602', exchange='NYMEX', currency='USD')
# Use distinct contracts for each CCI algorithm
cci14_compare_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202603', exchange='NYMEX', currency='USD')
cci14_120_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202511', exchange='NYMEX', currency='USD')
cci14_200_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202512', exchange='NYMEX', currency='USD')



FORCE_CLOSE_TIME = (22, 50)  # Daily force-close (HH, MM) applied to all algorithms


def instantiate_algorithms():
    """Create algorithm instances with a uniform daily force-close time. Returns list."""
    import time
    ema_algo = EMATradingAlgorithm(
        contract_params=ema_contract_params,
        client_id=22,
        ema_period=200,
        check_interval=60,
        initial_ema=80,
        signal_override=0,
        test_order_enabled=True,
        defer_connection=True,
        force_close=FORCE_CLOSE_TIME,
    )
    fib_algo = FibonacciTradingAlgorithm(
        contract_params=fib_contract_params,
        client_id=18,
        check_interval=60,
        fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786],
        test_order_enabled=True,
        defer_connection=True,
        force_close=FORCE_CLOSE_TIME,
    )
    cci14_compare_algo = CCI14_Compare_TradingAlgorithm(
        contract_params=cci14_compare_contract_params,
        client_id=19,
        check_interval=60,
        initial_ema=80,
        multi_ema_diagnostics=True,
        multi_ema_bootstrap=True,
        test_order_enabled=True,
        defer_connection=True,
        force_close=FORCE_CLOSE_TIME,
    )
    cci14_120_algo = CCI14_120_TradingAlgorithm(
        contract_params=cci14_120_contract_params,
        client_id=20,
        check_interval=60,
        initial_ema=80,
        cli_price=65.0,
        test_order_enabled=True,
        defer_connection=True,
        force_close=FORCE_CLOSE_TIME,
    )
    cci14_200_algo = CCI14_200_TradingAlgorithm(
        contract_params=cci14_200_contract_params,
        client_id=21,
        check_interval=60,
        initial_ema=80,
        trade_timezone="Asia/Jerusalem",
        trade_start=(8, 0),
        trade_end=(23, 0),  # Extended end of trading window to 23:00
        classic_cci=True,  # Enable classic (mean deviation) CCI for 200-threshold variant by default
        test_order_enabled=True,
        defer_connection=True,
        force_close=FORCE_CLOSE_TIME,
    )
    return [
        ema_algo,
        fib_algo,
        cci14_compare_algo,
        cci14_120_algo,
        cci14_200_algo,
    ]

# Stagger configuration: base seconds between thread starts plus optional jitter
STAGGER_BASE_SECONDS = 4  # adjust as needed
STAGGER_JITTER_SECONDS = 2  # set to 0 to disable random jitter

# Console selection:
# - By default, only CCI14_200_TradingAlgorithm logs to console; others file-only.
# - Override via env var CONSOLE_ALGOS as a comma-separated list of class names.
DEFAULT_CONSOLE_ALGOS = { 'CCI14_200_TradingAlgorithm' }
def _get_console_algos_from_env():
    raw = os.getenv('CONSOLE_ALGOS', '').strip()
    if not raw:
        return set(DEFAULT_CONSOLE_ALGOS)
    parts = [p.strip() for p in raw.split(',') if p.strip()]
    return set(parts) if parts else set(DEFAULT_CONSOLE_ALGOS)

def run_algo(algo):
    # Ensure this thread has an asyncio event loop for ib_insync compatibility
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    # Thread startup message
    try:
        algo.log("🧵 Thread started for algorithm runner")
    except Exception:
        pass
    algo.run()

import os
import sys
import time
import json
import subprocess
import urllib.request
import urllib.error
from typing import List, Tuple, Optional


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.getcode() < 300
    except Exception:
        return False


def _wait_for(url: str, name: str, timeout_sec: int = 90, interval: float = 2.0) -> bool:
    start = time.time()
    while time.time() - start < timeout_sec:
        if _http_ok(url):
            print(f"[Launcher] {name} is up: {url}")
            return True
        time.sleep(interval)
    print(f"[Launcher] Timeout waiting for {name} at {url}")
    return False


def _run(cmd: List[str], cwd: Optional[str] = None) -> Tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if proc.stdout:
            print(proc.stdout.rstrip())
        if proc.stderr:
            print(proc.stderr.rstrip())
        return proc.returncode, (proc.stdout or proc.stderr or '').strip()
    except Exception as e:
        print(f"[Launcher] Failed to run {' '.join(cmd)}: {e}")
        return 1, str(e)


def _docker_available() -> bool:
    """Return True if docker and docker compose are available, False otherwise."""
    try:
        rc, _out = _run(["docker", "--version"])
        if rc != 0:
            return False
        rc, _out = _run(["docker", "compose", "version"])
        return rc == 0
    except Exception:
        return False


def _bootstrap_observability_stack(repo_root: str) -> None:
    """Optionally start ES+Kibana, set up Discover view, and seed sample trades.

    Controlled by either env BOOTSTRAP_ES=1 or CLI flag --bootstrap-es.
    No-op if docker is unavailable.
    """
    es_url = os.getenv("ES_URL", "http://localhost:9200")
    kibana_url = os.getenv("KIBANA_URL", "http://localhost:5601")

    # If ES is already reachable, skip bringing up Docker to avoid churn
    if _http_ok(es_url):
        print(f"[Launcher] Elasticsearch already reachable at {es_url} — skipping docker compose up")
    else:
        if not _docker_available():
            print("[Launcher] Docker not available — skipping ES/Kibana bootstrap. Set TRADES_ES_ENABLED=0 to silence ES logs.")
            return
        docker_compose = ["docker", "compose", "-f", os.path.join(repo_root, "docker-compose.yml")]
        # Bring up stack
        print("[Launcher] Bootstrapping Elasticsearch + Kibana (docker compose up -d)…")
        rc, _ = _run(docker_compose + ["up", "-d"], cwd=repo_root)
        if rc != 0:
            print("[Launcher] Docker compose up failed — continuing without ES/Kibana")
            return

    # Wait for services
    _wait_for(f"{es_url}", "Elasticsearch", timeout_sec=120)
    # Kibana root may return HTML even before ready; ping status API if available
    kib_ready = _wait_for(f"{kibana_url}/api/status", "Kibana", timeout_sec=180)
    if not kib_ready:
        # Fallback to root
        _wait_for(f"{kibana_url}", "Kibana (fallback)", timeout_sec=30)

    # Run Kibana Discover setup
    print("[Launcher] Running Kibana Discover setup script…")
    _run([sys.executable, os.path.join(repo_root, "scripts", "setup_kibana_saved_search.py")], cwd=repo_root)

    # Seed ES with sample trades for visualization (only if empty by default)
    print("[Launcher] Seeding sample trades into Elasticsearch (if empty)…")
    _run([sys.executable, os.path.join(repo_root, "scripts", "seed_trades_es.py"), "--if-empty", os.getenv("TRADES_ES_INDEX", "trades")], cwd=repo_root)


def _should_bootstrap_from_args_env(argv: List[str]) -> bool:
    # Explicit opt-out takes precedence
    if "--no-bootstrap-es" in argv:
        return False
    if os.getenv("BOOTSTRAP_ES", "").lower() in ("0", "false", "no"):
        return False
    # Explicit opt-in
    if "--bootstrap-es" in argv:
        return True
    if os.getenv("BOOTSTRAP_ES", "").lower() in ("1", "true", "yes"):
        return True
    # Default: bootstrap enabled when running this launcher directly
    return True


if __name__ == "__main__":
    # Ensure console gets 10 blank lines at very top once per process (UX preference)
    try:
        # If base hasn't padded yet, do it here and set the guard to avoid double printing
        if not getattr(TradingAlgorithm, '_console_padded_once', False):
            print("\n" * 10, end="")
            TradingAlgorithm._console_padded_once = True
    except Exception:
        pass
    # Enable ES trade logging by default when running via this launcher
    try:
        os.environ.setdefault('TRADES_ES_ENABLED', '1')
        os.environ.setdefault('TRADES_ES_INDEX', 'trades')
    except Exception:
        pass
    # Optional: bootstrap ES+Kibana and set up Discover + seed data
    try:
        repo_root = os.path.dirname(os.path.abspath(__file__))
        if _should_bootstrap_from_args_env(sys.argv):
            _bootstrap_observability_stack(repo_root)
    except Exception as e:
        print(f"[Launcher] Observability bootstrap error: {e}")

    # Determine which algos should print to console, and set it before instantiation
    console_set = _get_console_algos_from_env()
    try:
        TradingAlgorithm.CONSOLE_ALLOWED = set(console_set)
    except Exception:
        pass
    algorithms = instantiate_algorithms()
    # Always run all instantiated algorithms; console output still limited by CONSOLE_ALGOS

    # Apply instance-level console preference (redundant but ensures runtime changes if needed)
    for algo in algorithms:
        algo.log_to_console = (type(algo).__name__ in console_set)
    try:
        running_names = ', '.join(type(a).__name__ for a in algorithms)
        print(f"[Launcher] All algorithms configured with daily force-close at {FORCE_CLOSE_TIME[0]:02d}:{FORCE_CLOSE_TIME[1]:02d}")
        print(f"[Launcher] Will run: {running_names}")
    except Exception:
        pass

    threads = []
    for idx, algo in enumerate(algorithms):
        if idx > 0:
            base = STAGGER_BASE_SECONDS
            jitter = random.uniform(0, STAGGER_JITTER_SECONDS) if STAGGER_JITTER_SECONDS > 0 else 0
            delay = base + jitter
            try:
                print(f"[Launcher] Staggering start of {type(algo).__name__} by {delay:.2f}s (idx={idx})")
            except Exception:
                pass
            time.sleep(delay)
        t = threading.Thread(target=run_algo, args=(algo,), name=f"AlgoThread-{type(algo).__name__}")
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
