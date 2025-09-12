import threading
import asyncio
import time
import random
from algorithms.ema_trading_algorithm import EMATradingAlgorithm
from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm
from algorithms.cci14_compare_trading_algorithm import CCI14_Compare_TradingAlgorithm
from algorithms.cci14_120_trading_algorithm import CCI14_120_TradingAlgorithm
from algorithms.cci14_200_trading_algorithm import CCI14_200_TradingAlgorithm



# Example contract parameters (customize as needed for each algo)
ema_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
fib_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202602', exchange='NYMEX', currency='USD')
# Use distinct contracts for each CCI algorithm
cci14_compare_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202512', exchange='NYMEX', currency='USD')
cci14_120_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202511', exchange='NYMEX', currency='USD')
cci14_200_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202510', exchange='NYMEX', currency='USD')



# Instantiate algorithm objects (add others as you refactor them)
ema_algo = EMATradingAlgorithm(contract_params=ema_contract_params, client_id=22,
    ema_period=200, check_interval=60, initial_ema=80, signal_override=0,
    test_order_enabled=True, defer_connection=True)
fib_algo = FibonacciTradingAlgorithm(contract_params=fib_contract_params, client_id=18,
    check_interval=60, fib_levels=[0.236,0.382,0.5,0.618,0.786],
    test_order_enabled=True, defer_connection=True)

cci14_compare_algo = CCI14_Compare_TradingAlgorithm(contract_params=cci14_compare_contract_params, client_id=19,
    check_interval=60, initial_ema=80, test_order_enabled=True, defer_connection=True)

cci14_120_algo = CCI14_120_TradingAlgorithm(contract_params=cci14_120_contract_params, client_id=20,
    check_interval=60, initial_ema=80, cli_price=65.0,
    test_order_enabled=True, defer_connection=True)

cci14_200_algo = CCI14_200_TradingAlgorithm(contract_params=cci14_200_contract_params, client_id=21,
    check_interval=60, initial_ema=80, trade_timezone="Asia/Jerusalem",
    trade_start=(8,0), trade_end=(20,0), test_order_enabled=True, defer_connection=True)



# List of all algorithm objects to run
algorithms = [ema_algo, fib_algo, cci14_compare_algo, cci14_120_algo, cci14_200_algo]  # Add others as you implement them

# Stagger configuration: base seconds between thread starts plus optional jitter
STAGGER_BASE_SECONDS = 4  # adjust as needed
STAGGER_JITTER_SECONDS = 2  # set to 0 to disable random jitter

# Choose one algorithm to also log to console; all others log to file only
CONSOLE_ALGO = 'EMATradingAlgorithm'  # changed to make EMA console-visible
for algo in algorithms:
    algo.log_to_console = (type(algo).__name__ == CONSOLE_ALGO)

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

if __name__ == "__main__":
    threads = []
    for idx, algo in enumerate(algorithms):
        # Optional stagger delay before starting each subsequent algorithm
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
