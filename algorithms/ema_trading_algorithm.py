from algorithms.trading_algorithms_class import TradingAlgorithm
import math
import datetime
import json
import time

class EMATradingAlgorithm(TradingAlgorithm):
	def __init__(self, contract_params, ema_period, check_interval, initial_ema, signal_override, tick_size: float = 0.01, sl_ticks: int = 17, tp_ticks_long: int = 28, tp_ticks_short: int = 35, diagnostics_enabled=False, diagnostics_every=5, ib=None, **kwargs):
		"""EMA strategy with optional extended diagnostics.

		Parameters:
		- contract_params (dict)
		- ema_period (int)
		- check_interval (int seconds)
		- initial_ema (float)
		- signal_override (int: -1 short, 0 none, 1 long)
		- diagnostics_enabled (bool) default False so tests & perf unaffected.
		- diagnostics_every (int) log diagnostics every N ticks when enabled.
		"""
		# Call base initializer first (does not know about diagnostics params)
		super().__init__(contract_params, ib=ib, **kwargs)
		# Ensure EMA algorithm logs to console (designated console-visible strategy)
		self.log_to_console = True
		self.EMA_PERIOD = ema_period

		# ✅ Configure base class to handle EMA200  
		self.EMA_SLOW_PERIOD = ema_period  # This will be 200
		self.ema_slow = initial_ema  # Initialize base class EMA
		
		# ✅ Disable automatic EMA updates since we handle them manually
		self.auto_update_ema = False

		self.K = 2 / (self.EMA_PERIOD + 1)
		self.CHECK_INTERVAL = check_interval
		self.signal_override = signal_override
		self.long_ready = self.short_ready = False
		self.long_counter = self.short_counter = 0
		self.paused_notice_shown = False
		self.TICK_SIZE = tick_size
		self.SL_TICKS = sl_ticks
		self.TP_TICKS_LONG = tp_ticks_long
		self.TP_TICKS_SHORT = tp_ticks_short
		self.QUANTITY = 1
		# Historical seeding configuration
		self.seeding_complete = False
		self.required_closes = 215
		self._original_ema = initial_ema  # Track original for logging
		# Diagnostics configuration (kept for compatibility, no-op now that base handles EMA diagnostics)
		self.diagnostics_enabled = diagnostics_enabled
		self.diagnostics_every = max(1, int(diagnostics_every)) if diagnostics_enabled else diagnostics_every
		# No extra per-tick diagnostics are emitted by this class anymore; rely on base logging

	def process_candle(self, price, ema_value, time_str="", is_historical=False):
		"""Shared candle logic for both historical seeding and live trading"""
		if price > ema_value:
			self.long_counter += 1
			self.short_counter = 0
			signal_type = "LONG"
			if not is_historical:
				self.log(f"{time_str} 📈 LONG candle #{self.long_counter}")
			if self.long_counter >= 15 and not self.long_ready:
				self.long_ready = True
				if not is_historical:
					self.log(f"{time_str} ✅ LONG setup ready")
		elif price < ema_value:
			self.short_counter += 1
			self.long_counter = 0
			signal_type = "SHORT"
			if not is_historical:
				self.log(f"{time_str} 📉 SHORT candle #{self.short_counter}")
			if self.short_counter >= 15 and not self.short_ready:
				self.short_ready = True
				if not is_historical:
					self.log(f"{time_str} ✅ SHORT setup ready")
		else:
			signal_type = "NEUTRAL"
			if not is_historical:
				self.log(f"{time_str} ⚖️ NEUTRAL candle — counters reset")
		return signal_type

	def handle_seeding(self):
		"""Handle historical seeding process"""
		close_history = getattr(self, 'close_history', [])
		if len(close_history) >= self.required_closes:
			self.log(f"📊 Starting EMA seeding process...")
			if self.process_historical_candles():
				self.log("✅ EMA seeding complete - ready for live trading")
			else:
				self.log("❌ EMA seeding failed")
				self.seeding_complete = True
			return True
		else:
			self.log(f"📊 Collecting closes: {len(close_history)}/{self.required_closes}")
			if len(close_history) > 0:
				recent_closes = close_history[-min(5, len(close_history)):]
				self.log(f"📊 Recent closes: {[f'{c:.2f}' for c in recent_closes]}")
			return True

	def process_historical_candles(self):
		"""Process the last 15 closes from seeded data using shared candle logic"""
		
		close_history = getattr(self, 'close_history', [])
		
		if len(close_history) < self.required_closes:
			self.log(f"⚠️ Insufficient closes history: {len(close_history)} closes (need {self.required_closes})")
			return False
			
		self.log(f"📊 Starting EMA seeding with {len(close_history)} closes")
		self.log(f"📊 Processing last 15 candles to initialize counters")
		
		# Reset counters before historical processing
		self.long_counter = 0
		self.short_counter = 0
		
		# Take the last 15 closes for analysis
		last_15_closes = close_history[-15:]

		# Debug: Show the actual last 15 closes
		self.log(f"📊 Last 15 historical closes:")
		for i, close in enumerate(last_15_closes):
			self.log(f"   #{i+1}: {close:.4f}")

		final_ema = None  # Track the final EMA value
		
		for i, close_price in enumerate(last_15_closes):
			candle_num = i + 1
			
			# Calculate available data up to this historical point
			if i < 14:
				available_data = close_history[:-(15-i)]
			else:
				available_data = close_history[:]

            # Use exactly the last 200 points for EMA calculation
			if len(available_data) >= 200:
				ema_data = available_data[-200:]
				ema_200 = self._calculate_ema_from_data(ema_data)
				final_ema = ema_200  # Save the final EMA value
                				
				# Log historical candle details
				self.log(f"📊 Candle {candle_num:2d}/15:")
				self.log(f"   📈 Historical Close: {close_price:.4f} (from position {len(close_history)-15+i})")
				self.log(f"   📊 EMA200: {ema_200:.4f}")
				
				# Use shared candle processing logic
				signal_type = self.process_candle(close_price, ema_200, is_historical=True)
				
				self.log(f"   🎯 Signal: {close_price:.4f} {'>' if signal_type == 'LONG' else '<' if signal_type == 'SHORT' else '='} {ema_200:.4f} → {signal_type}")
				self.log(f"   📊 Counters: LONG={self.long_counter}, SHORT={self.short_counter}")
				
			else:
				self.log(f"📊 Candle {candle_num:2d}/15: Insufficient data ({len(available_data)}/200)")
		# ✅ CRITICAL FIX: Update live_ema with the final calculated EMA
		if final_ema is not None:
			old_ema = self.ema_slow
			self.ema_slow = final_ema # Use base class EMA
			self.log(f"📊 Updated ema_slow from {old_ema:.4f} to {final_ema:.4f}")
 		
		self.log(f"")
		self.log(f"✅ EMA Historical Seeding Complete:")
		self.log(f"   📊 Final Counters: LONG={self.long_counter}, SHORT={self.short_counter}")
		self.log(f"   🚀 Ready to start at candle 16")
		self.log(f"")
		
		self.seeding_complete = True
		return True

	def _calculate_ema_from_data(self, price_data):
		"""Calculate EMA 200 from exactly 200 historical price points using existing formula"""
		if len(price_data) != 200:
			self.log(f"❌ EMA calculation error: expected 200 points, got {len(price_data)}")
			return None
		
		# Start with SMA of first 20 periods
		sma = sum(price_data[:20]) / 20
		ema = sma
		
		# Apply EMA calculation using existing multiplier
		for price in price_data[20:]:
			ema = (price - ema) * self.K + ema
			
		return ema

	def execute_trade(self, action, time_str, price, is_override=False):
		"""Execute trade and reset state"""
		self.place_bracket_order(action, self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
		if action == 'BUY':
			self.long_ready = False
			self.long_counter = 0
		else:
			self.short_ready = False
			self.short_counter = 0
		self.signal_override = 0
		override_text = "override " if is_override else ""
		self.log(f"{time_str} ✅ {action} {override_text}entry executed @ {price}")
	
	def on_tick(self, time_str):
		
		has_position = self.has_active_position()

		self.on_tick_common(time_str, active_position=has_position)
		# Handle historical seeding if needed
		if not self.seeding_complete:
			if self.handle_seeding():
				return

		ctx = self.tick_prologue(
			time_str,
			update_ema=False, # ✅ Disable base class EMA updates completely
			compute_cci=False,
			price_annotator=lambda: {"EMA": self.ema_slow}, # Use base class EMA
		)
		if ctx is None:
			return
		
		price = ctx["price"]

    	# Manually update EMA from seeded value (don't use base class)
		self.ema_slow = (price - self.ema_slow) * self.K + self.ema_slow

        # Log checking trade conditions
		self.log_checking_trade_conditions(time_str)

		if not has_position:	
			# Standard counter logic - now using shared method
			self.process_candle(price, self.ema_slow, time_str, is_historical=False)
			
			# Entry conditions
			if self.long_ready and not has_position and price < self.ema_slow:
				self.execute_trade('BUY', time_str, price)
			elif self.short_ready and not has_position and price > self.ema_slow:
				self.execute_trade('SELL', time_str, price)
		else:
			self.log(f"{time_str} 🚫 BLOCKED: Trade already active")
		self.log("\n")

	def reset_state(self):
		self.signal_override = 0
		self.long_ready = False
		self.short_ready = False
		self.long_counter = 0
		self.short_counter = 0
		self.seeding_complete = False
