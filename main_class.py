import threading
import asyncio
from algorithms.ema_trading_algorithm import EMATradingAlgorithm
from algorithms.fibonacci_trading_algorithm import FibonacciTradingAlgorithm
from algorithms.cci14_trading_algorithm import CCI14TradingAlgorithm
from algorithms.cci14rev_trading_algorithm import CCI14RevTradingAlgorithm
from algorithms.cci14threshold_trading_algorithm import CCI14ThresholdTradingAlgorithm



# Example contract parameters (customize as needed for each algo)
ema_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202601', exchange='NYMEX', currency='USD')
fib_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202602', exchange='NYMEX', currency='USD')
# Use distinct contracts for each CCI algorithm
cci14_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202512', exchange='NYMEX', currency='USD')
cci14rev_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202511', exchange='NYMEX', currency='USD')
cci14threshold_contract_params = dict(symbol='CL', lastTradeDateOrContractMonth='202510', exchange='NYMEX', currency='USD')



# Instantiate algorithm objects (add others as you refactor them)
ema_algo = EMATradingAlgorithm(
    contract_params=ema_contract_params,
    ema_period=200,
    check_interval=60,
    initial_ema=80,  # Example value, replace as needed
    signal_override=0,
    client_id=17
)
fib_algo = FibonacciTradingAlgorithm(
    contract_params=fib_contract_params,
    check_interval=60,
    fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786],
    client_id=18
)

cci_algo = CCI14TradingAlgorithm(
    contract_params=cci14_contract_params,
    check_interval=60,
    initial_ema=80,  # Example value, replace as needed
    client_id=19
)

cci14rev_algo = CCI14RevTradingAlgorithm(
    contract_params=cci14rev_contract_params,
    check_interval=60,
    initial_ema=80,  # Example value, replace as needed
    client_id=20
)

cci14threshold_algo = CCI14ThresholdTradingAlgorithm(
    contract_params=cci14threshold_contract_params,
    check_interval=60,
    initial_ema=80,
    trade_timezone="Asia/Jerusalem",
    trade_start=(8, 0),
    trade_end=(20, 0),
    client_id=21
)



# List of all algorithm objects to run
algorithms = [ema_algo, fib_algo, cci_algo, cci14rev_algo, cci14threshold_algo]  # Add others as you implement them

def run_algo(algo):
    # Ensure this thread has an asyncio event loop for ib_insync compatibility
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    algo.run()

if __name__ == "__main__":
    threads = []
    for algo in algorithms:
        t = threading.Thread(target=run_algo, args=(algo,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
