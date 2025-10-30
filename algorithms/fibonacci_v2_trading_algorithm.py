from algorithms.trading_algorithms_class import TradingAlgorithm
import datetime
from statistics import mean

class FibonacciV2TradingAlgorithm(TradingAlgorithm):
    def __init__(self, contract_params, check_interval, fib_levels=None, 
                 TICK_SIZE: float = 0.01, SL_TICKS: int = 20, TP_TICKS_LONG: int = 30, TP_TICKS_SHORT: int = 30, QUANTITY: int = 1, **kwargs):
        # Remove trading parameters from kwargs before passing to parent
        filtered_kwargs = {k: v for k, v in kwargs.items() 
                          if k not in ['TICK_SIZE', 'SL_TICKS', 'TP_TICKS_LONG', 'TP_TICKS_SHORT', 'QUANTITY']}
        super().__init__(contract_params, **filtered_kwargs)
        
        self.CHECK_INTERVAL = check_interval
        self.fib_levels = fib_levels or [0.236, 0.382, 0.5, 0.618, 0.786]
        # Store trading parameters
        self.TICK_SIZE = TICK_SIZE
        self.SL_TICKS = SL_TICKS
        self.TP_TICKS_LONG = TP_TICKS_LONG
        self.TP_TICKS_SHORT = TP_TICKS_SHORT
        self.QUANTITY = QUANTITY
        self.price_history = []
        self.daily_bars = []  # Separate list for daily bar data
        self.active_direction = None
        self.trade_active = False
        self.active_tp_price = None
        self.active_stop_price = None
        self.active_fib_index = None
        self.level_engaged = False
        self.prev_price = None
        self.initial_direction = None  # 'BULLISH' or 'BEARISH'
        self.fib_high = None
        self.fib_low = None
        self.last_daily_update = None

    def calculate_fibonacci_levels(self, high, low, is_bullish):
        if high is None or low is None or high == low:
            return []
        diff = high - low
        if is_bullish:
            return [round(high - diff * r, 2) for r in self.fib_levels]
        else:
            return [round(low + diff * r, 2) for r in self.fib_levels]
    def execute_fibonacci_entry(self, direction, action, level, fib_ratio, time_str, prev_price, price, signal_type):
        """Execute Fibonacci entry and set trade state"""
        self.log(f"{time_str} {'📈' if action == 'BUY' else '📉'} {direction} SIGNAL: {signal_type} {fib_ratio*100:.1f}% {'resistance' if 'resistance' in signal_type.lower() else 'support'} @ {level}")
        self.log(f"{time_str} 🎯 Entry Logic: {prev_price:.2f} {'<' if prev_price < level else '>'} {level:.2f} {'<' if price < level else '>'} {price:.2f}")
        
        self.place_bracket_order(action, self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
        self.active_direction = direction
        self.active_fib_index = getattr(self, '_current_fib_index', 0)
        self.level_engaged = True
        self.trade_active = True
    
    def check_fibonacci_entry(self, direction, fib_levels_classified, prev_price, price, time_str):
        """Check for Fibonacci entry signals based on direction"""
        for i, (level, label) in enumerate(fib_levels_classified):
            self._current_fib_index = i  # Store for execute_fibonacci_entry
            is_last_level = (level == fib_levels_classified[-1][0])
            is_first_level = (level == fib_levels_classified[0][0])
            fib_ratio = self.fib_levels[i] if i < len(self.fib_levels) else 0
            
            if direction == 'BULLISH':
                # Breakout above resistance
                if prev_price < level and price > level and not is_last_level:
                    self.execute_fibonacci_entry('LONG', 'BUY', level, fib_ratio, time_str, prev_price, price, 'Breakout above')
                    return True
                # Pullback to support  
                elif prev_price > level and price < level and not is_first_level:
                    self.execute_fibonacci_entry('LONG', 'BUY', level, fib_ratio, time_str, prev_price, price, 'Pullback to')
                    return True
                    
            elif direction == 'BEARISH':
                # Breakdown below support
                if prev_price > level and price < level and not is_first_level:
                    self.execute_fibonacci_entry('SHORT', 'SELL', level, fib_ratio, time_str, prev_price, price, 'Breakdown below')
                    return True
                # Pullback to resistance
                elif prev_price < level and price > level and not is_last_level:
                    self.execute_fibonacci_entry('SHORT', 'SELL', level, fib_ratio, time_str, prev_price, price, 'Pullback to')
                    return True
                    
        return False
        
    def request_daily_bars(self):
        """Request daily bars and update Fibonacci levels based on previous day's candle"""
        try:
            bars = self.ib.reqHistoricalData(
                self.contract,
                endDateTime='',
                durationStr='12 D',  # Request 12 days to ensure at least 10 candles (accounting for weekends)
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=False
            )
            
            if not bars or len(bars) < 10:
                self.log(f"⚠️ Only {len(bars) if bars else 0} daily candles available — need at least 10")
                return False
                
            self.daily_bars = list(bars)
            
            # Log 61.8% Fibonacci level for last 10 days (matching original snippet)
            if len(self.daily_bars) >= 10:
                self.log("📊 61.8% Fibonacci Level per Daily Candle (Last 10 Days):")
                for i, bar in enumerate(self.daily_bars[-10:]):
                    high = bar.high
                    low = bar.low
                    is_bullish = bar.close > bar.open
                    fib_61_8 = round(high - (high - low) * 0.618, 2) if is_bullish else round(low + (high - low) * 0.618, 2)
                    date_str = bar.date.strftime('%Y-%m-%d')
                    self.log(f"{i+1}. {date_str} → 61.8%: {fib_61_8}")
            
            # Use previous day's candle for main Fibonacci calculation
            prev_bar = self.daily_bars[-2]  # Previous day's candle
            
            # Determine direction from previous day's candle
            is_bullish = prev_bar.close > prev_bar.open
            self.initial_direction = 'BULLISH' if is_bullish else 'BEARISH'
            self.fib_high = prev_bar.high
            self.fib_low = prev_bar.low
            
            self.log(f"\n�️ Previous Daily Candle Details:")
            self.log(f"   Date     : {prev_bar.date.strftime('%A %Y-%m-%d')}")
            self.log(f"   Open     : {prev_bar.open}")
            self.log(f"   High     : {prev_bar.high}")
            self.log(f"   Low      : {prev_bar.low}")
            self.log(f"   Close    : {prev_bar.close}")
            self.log(f"   Direction: {self.initial_direction}")
            
            return True
            
        except Exception as e:
            self.log(f"❌ Error requesting daily bars: {e}")
            return False

    def on_tick(self, time_str):
         
        self.on_tick_common(time_str)
        ctx = self.tick_prologue(
            time_str,
            update_ema=True,
            compute_cci=True,  # Compute CCI for completeness
            price_annotator=None,
        )
        if ctx is None:
            return
        price = ctx["price"]
        # Request daily bars if not done recently (once per day or on startup)
        now = datetime.datetime.now()
        if self.last_daily_update is None or (now.date() > self.last_daily_update.date()):
            if self.request_daily_bars():
                self.last_daily_update = now
            else:
                return  # Skip if daily bars request failed
        
        # Calculate Fibonacci levels from daily bars
        if self.fib_high is None or self.fib_low is None or self.initial_direction is None:
            return  # Skip if daily data not available
            
        # Standard condition-eval log
        self.log_checking_trade_conditions(time_str)
            
        is_bullish = (self.initial_direction == 'BULLISH')
        fib_levels = self.calculate_fibonacci_levels(self.fib_high, self.fib_low, is_bullish)
        
        if not fib_levels:
            self.log(f"{time_str} ❌ No Fibonacci levels calculated - skipping")
            return
        
        # Log Fibonacci calculation details
        range_size = self.fib_high - self.fib_low
        self.log(f"{time_str} 📐 Fibonacci Calculation: H={self.fib_high}, L={self.fib_low}, Range={range_size:.2f}, Direction={self.initial_direction}")
            
        # Sort levels from high to low for consistency with original code
        fib_levels = sorted(fib_levels, reverse=True)
        
        # Classify levels based on current price position
        all_above = all(price > level for level in fib_levels)
        all_below = all(price < level for level in fib_levels)
        
        self.log(f"{time_str} 🎯 Current Price: {price} | Position: {'Above All' if all_above else 'Below All' if all_below else 'Between Levels'}")
        
        fib_levels_classified = []
        for i, level in enumerate(fib_levels):
            if all_above:
                label = 'Support'
            elif all_below:
                label = 'Resistance'
            else:
                label = 'Support' if price > level else 'Resistance'
            fib_levels_classified.append((level, label))
            
        # Log all classified levels for debugging
        self.log(f"{time_str} 📊 Fibonacci Levels:")
        for i, (level, label) in enumerate(fib_levels_classified):
            ratio = self.fib_levels[i] if i < len(self.fib_levels) else 'N/A'
            self.log(f"   {level:.2f} ({ratio*100:.1f}%) → {label}")
        
        # Market direction flip logic
        if self.initial_direction == 'BULLISH' and all_below:
            self.initial_direction = 'BEARISH'
            self.log("🔄 Market flipped to BEARISH — price below all levels")
        elif self.initial_direction == 'BEARISH' and all_above:
            self.initial_direction = 'BULLISH'
            self.log("🔄 Market flipped to BULLISH — price above all levels")
        
        # Track previous price for breakout/breakdown logic
        prev_price = self.prev_price
        self.prev_price = price
        
        if prev_price is not None:
            price_change = price - prev_price
            self.log(f"{time_str} 📈 Price Movement: {prev_price:.2f} → {price:.2f} (Δ{price_change:+.2f})")
        
        # Entry logic based on original snippet
        if not self.trade_active and prev_price is not None:
            self.check_fibonacci_entry(self.initial_direction, fib_levels_classified, prev_price, price, time_str)        
 
        # Log no signal if no entry was triggered
        if not self.trade_active:
            self.log(f"{time_str} 🔍 No Fibonacci signal at the moment.\n")
                
        # Add spacing after tick processing
        self.log("")

    def reset_state(self):
        self.active_direction = None
        self.active_tp_price = None
        self.active_stop_price = None
        self.trade_active = False
        self.active_fib_index = None
        self.level_engaged = False
        self.prev_price = None
