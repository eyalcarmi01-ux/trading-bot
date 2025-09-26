from algorithms.trading_algorithms_class import TradingAlgorithm
import datetime


class FibonacciTradingAlgorithm(TradingAlgorithm):
	def __init__(self, contract_params, check_interval, fib_levels, ib=None, use_prev_daily_candle=False, ma120_manual_override=None, **kwargs):
		"""
		client_id (int): Pass as a kwarg to ensure unique IB connection per instance.
		ib: Pass a mock IB instance for testing.
		use_prev_daily_candle: If True, use legacy behavior based on previous daily candle's Fibonacci levels.
		ma120_manual_override: Optional float fallback for 120-hour MA when insufficient data.
		"""
		super().__init__(contract_params, ib=ib, **kwargs)
		self.CHECK_INTERVAL = check_interval
		self.fib_levels = fib_levels  # e.g. [0.236, 0.382, 0.5, 0.618, 0.786]
		# Session-based retracement tracking (default behavior for tests)
		self.last_high = None
		self.last_low = None
		self.last_signal = None
		# Order params
		self.TICK_SIZE = 0.01
		self.SL_TICKS = 17
		self.TP_TICKS_LONG = 28
		self.TP_TICKS_SHORT = 35
		self.QUANTITY = 1
		# Computed levels for session-mode
		self.fib_retracements = []
		# Legacy daily-candle mode state
		self.use_prev_daily_candle = use_prev_daily_candle
		self.is_bullish = None
		self.fib_high = None
		self.fib_low = None
		self.fib_levels_prices = []
		self.fib_target = None
		self.fib_type = None  # 'Support' or 'Resistance'
		self.hourly_closes = []
		self.ma_120_hourly = None
		self.ma120_manual_override = ma120_manual_override
		# Trade-state tracking for legacy-style reversal logic
		self.trade_active = False
		self.active_direction = None  # 'LONG' | 'SHORT'
		self.active_stop_price = None
		self.active_tp_price = None
		self.last_stop_direction = None
		# Feature flags (parity with legacy script):
		#  - verbose_legacy_status: multi-line status block & separator each legacy tick
		self.verbose_legacy_status = bool(use_prev_daily_candle)  # only for legacy mode


	def pre_run(self):
		"""Optional warm-up: fetch previous daily candle and hourly MA for legacy mode."""
		if not self.use_prev_daily_candle:
			return
		try:
			# Determine today's/yesterday's date and fetch 2 daily bars
			today = datetime.datetime.now().date()
			bars_daily = self.ib.reqHistoricalData(
				self.contract,
				endDateTime=today.strftime('%Y%m%d 00:00:00'),
				durationStr='2 D',
				barSizeSetting='1 day',
				whatToShow='TRADES',
				useRTH=True
			)
			# Log concise summary
			try:
				count = len(bars_daily) if bars_daily is not None else 0
				def _bar_desc(b):
					date = getattr(b, 'date', None) or getattr(b, 'time', None)
					close = getattr(b, 'close', None)
					if date is not None:
						return f"({date}, close={close})"
					return f"(close={close})"
				sample = ", ".join(_bar_desc(b) for b in list(bars_daily)[-2:]) if count else ""
				self.log(f"🗄️ Fib daily history: duration=2 D | bars={count} | sample={sample}")
			except Exception:
				pass
			if len(bars_daily) < 2:
				self.log("⚠️ Not enough daily candles — legacy fib mode disabled")
				self.use_prev_daily_candle = False
				return
			prev_bar = bars_daily[-2]
			self.is_bullish = prev_bar.close > prev_bar.open
			self.fib_high = prev_bar.high
			self.fib_low = prev_bar.low
			self.log(f"📅 Prev Daily: OPEN={prev_bar.open} | CLOSE={prev_bar.close} | {'POSITIVE' if self.is_bullish else 'NEGATIVE'}")
			# Compute fib level prices from previous candle
			self.fib_levels_prices = [
				round(self.fib_low + (self.fib_high - self.fib_low) * r, 2) if self.is_bullish else round(self.fib_high - (self.fib_high - self.fib_low) * r, 2)
				for r in self.fib_levels
			]
			self.log(f"📐 Fibonacci {'Support' if self.is_bullish else 'Resistance'} Levels: {self.fib_levels_prices}")
			# Choose the 61.8% level when available; otherwise use the last provided
			fib_idx = None
			try:
				fib_idx = self.fib_levels.index(0.618)
			except ValueError:
				fib_idx = len(self.fib_levels_prices) - 1 if self.fib_levels_prices else None
			if fib_idx is not None and fib_idx >= 0:
				self.fib_target = self.fib_levels_prices[fib_idx]
				self.fib_type = 'Support' if self.is_bullish else 'Resistance'
			# Fetch hourly candles for MA120h with fallback
			bars_hourly = []
			try:
				bars_hourly = self.ib.reqHistoricalData(
					self.contract,
					endDateTime='',
					durationStr='120 H',
					barSizeSetting='1 hour',
					whatToShow='TRADES',
					useRTH=True
				)
				# Log concise summary
				try:
					count = len(bars_hourly) if bars_hourly is not None else 0
					def _bar_desc(b):
						date = getattr(b, 'date', None) or getattr(b, 'time', None)
						close = getattr(b, 'close', None)
						if date is not None:
							return f"({date}, close={close})"
						return f"(close={close})"
					sample = ", ".join(_bar_desc(b) for b in list(bars_hourly)[-3:]) if count else ""
					self.log(f"🗄️ Fib hourly history: duration=120 H | bars={count} | sample={sample}")
				except Exception:
					pass
			except Exception as e:
				self.log(f"⚠️ Error fetching hourly candles: {e}")
			if len(bars_hourly) < 120:
				self.log("🔁 Fallback: requesting 3 days of hourly candles…")
				try:
					bars_hourly = self.ib.reqHistoricalData(
						self.contract,
						endDateTime='',
						durationStr='3 D',
						barSizeSetting='1 hour',
						whatToShow='TRADES',
						useRTH=True
					)
					# Log concise summary
					try:
						count = len(bars_hourly) if bars_hourly is not None else 0
						def _bar_desc(b):
							date = getattr(b, 'date', None) or getattr(b, 'time', None)
							close = getattr(b, 'close', None)
							if date is not None:
								return f"({date}, close={close})"
							return f"(close={close})"
						sample = ", ".join(_bar_desc(b) for b in list(bars_hourly)[-3:]) if count else ""
						self.log(f"🗄️ Fib hourly history (fallback): duration=3 D | bars={count} | sample={sample}")
					except Exception:
						pass
				except Exception as e:
					self.log(f"❌ Fallback request failed: {e}")
			if len(bars_hourly) < 120:
				if self.ma120_manual_override is not None:
					self.ma_120_hourly = float(self.ma120_manual_override)
					self.log(f"⚠️ Not enough hourly candles ({len(bars_hourly)}/120) — using manual override: {self.ma_120_hourly}")
				else:
					# Use whatever is available to compute a simple mean as best effort
					hourly_closes = [bar.close for bar in bars_hourly[-120:]]
					self.ma_120_hourly = round(sum(hourly_closes) / len(hourly_closes), 4) if hourly_closes else None
					self.log(f"⚠️ Not enough hourly candles ({len(bars_hourly)}/120) — computed partial MA: {self.ma_120_hourly}")
			else:
				hourly_closes = [bar.close for bar in bars_hourly[-120:]]
				self.ma_120_hourly = round(sum(hourly_closes) / len(hourly_closes), 4)
				self.log(f"📊 120-Hour Moving Average: {self.ma_120_hourly}")
			self.hourly_closes = [bar.close for bar in bars_hourly[-120:]]
		except Exception as e:
			self.log(f"❌ pre_run error (legacy mode): {e}")

	def _compute_tp_sl(self, action, entry_price):
		if action.upper() == 'BUY':
			return (
				round(entry_price + self.TICK_SIZE * self.TP_TICKS_LONG, 2),
				round(entry_price - self.TICK_SIZE * self.SL_TICKS, 2)
			)
		elif action.upper() == 'SELL':
			return (
				round(entry_price - self.TICK_SIZE * self.TP_TICKS_SHORT, 2),
				round(entry_price + self.TICK_SIZE * self.SL_TICKS, 2)
			)
		else:
			return None, None

	def on_tick(self, time_str):
		self.on_tick_common(time_str)
		ctx = self.tick_prologue(
			time_str,
			update_ema=False,
			compute_cci=False,
			price_annotator=None,
			update_history=False,
		)
		if ctx is None:
			return
		price = ctx["price"]

		# Legacy mode: previous daily candle fib targeting and 120h MA context
		if self.use_prev_daily_candle and self.fib_target is not None:
			# Maintain rolling MA120h list; append current_price as surrogate for freshest hourly close
			self.hourly_closes.append(price)
			if len(self.hourly_closes) > 120:
				self.hourly_closes = self.hourly_closes[-120:]
			if self.hourly_closes:
				self.ma_120_hourly = round(sum(self.hourly_closes) / len(self.hourly_closes), 4)
			# Decide planned action and entry condition vs the 61.8% level
			if self.is_bullish:
				planned_action = 'LONG'
				entry_condition_met = price <= self.fib_target
				fib_target = self.fib_target
			else:
				planned_action = 'SHORT'
				entry_condition_met = price >= self.fib_target
				fib_target = self.fib_target
			# Active trade monitoring (legacy-style TP/SL checks)
			if self.trade_active:
				if self.active_direction == 'LONG':
					if self.active_stop_price is not None and price <= self.active_stop_price:
						self.log(f"🛑 SL hit at {price:.2f} — closing LONG")
						self.close_all_positions()
						self.cancel_all_orders()
						self.trade_active = False
						self.last_stop_direction = 'LONG'
						self.active_direction = None
						self.active_stop_price = None
						self.active_tp_price = None
						return
					elif self.active_tp_price is not None and price >= self.active_tp_price:
						self.log(f"✅ TP hit at {price:.2f} — closing LONG")
						self.close_all_positions()
						self.cancel_all_orders()
						self.trade_active = False
						self.active_direction = None
						self.active_stop_price = None
						self.active_tp_price = None
						return
				elif self.active_direction == 'SHORT':
					if self.active_stop_price is not None and price >= self.active_stop_price:
						self.log(f"🛑 SL hit at {price:.2f} — closing SHORT")
						self.close_all_positions()
						self.cancel_all_orders()
						self.trade_active = False
						self.last_stop_direction = 'SHORT'
						self.active_direction = None
						self.active_stop_price = None
						self.active_tp_price = None
						return
					elif self.active_tp_price is not None and price <= self.active_tp_price:
						self.log(f"✅ TP hit at {price:.2f} — closing SHORT")
						self.close_all_positions()
						self.cancel_all_orders()
						self.trade_active = False
						self.active_direction = None
						self.active_stop_price = None
						self.active_tp_price = None
						return
			# No active position — can we enter?
			# Use base pending-aware gating: treat positions or working orders as active
			if entry_condition_met and not self.has_active_position():
				self.log(f"⚡ Price {price:.2f} meets {planned_action} condition at {fib_target:.2f}")
				# Pre-compute TP/SL at decision time to mirror legacy logs
				if planned_action == 'LONG':
					tp, sl = self._compute_tp_sl('BUY', price)
					self.active_tp_price, self.active_stop_price = tp, sl
					self.active_direction = 'LONG'
					self.trade_active = True
					self.place_bracket_order('BUY', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				else:
					tp, sl = self._compute_tp_sl('SELL', price)
					self.active_tp_price, self.active_stop_price = tp, sl
					self.active_direction = 'SHORT'
					self.trade_active = True
					self.place_bracket_order('SELL', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				return
			# Reversal logic after SL
			if self.last_stop_direction == 'LONG' and not self.has_active_position():
				if price >= self.fib_target:
					self.log(f"🔄 Reversal: Entering SHORT after failed LONG at {self.fib_target:.2f}")
					tp, sl = self._compute_tp_sl('SELL', price)
					self.active_tp_price, self.active_stop_price = tp, sl
					self.active_direction = 'SHORT'
					self.trade_active = True
					self.place_bracket_order('SELL', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
					self.last_stop_direction = None
					return
			if self.last_stop_direction == 'SHORT' and not self.has_active_position():
				if price <= self.fib_target:
					self.log(f"🔄 Reversal: Entering LONG after failed SHORT at {self.fib_target:.2f}")
					tp, sl = self._compute_tp_sl('BUY', price)
					self.active_tp_price, self.active_stop_price = tp, sl
					self.active_direction = 'LONG'
					self.trade_active = True
					self.place_bracket_order('BUY', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
					self.last_stop_direction = None
					return
			# Status log (compact)
			pos = 'ACTIVE' if self.trade_active else 'IDLE'
			dir_ = self.active_direction if self.trade_active else '—'
			tp = self.active_tp_price if self.trade_active else '—'
			sl = self.active_stop_price if self.trade_active else '—'
			# Verbose legacy-style multi-line block
			if self.verbose_legacy_status:
				self.log(f" {time_str} | Price: {price:.2f} | MA120h: {self.ma_120_hourly if self.ma_120_hourly is not None else 'n/a'}")
				self.log(f" Fibonacci {self.fib_type or 'n/a'} Target: {self.fib_target if self.fib_target is not None else 'n/a'} | Planned Action: {planned_action}")
				self.log(f" Position: {pos} | Direction: {dir_} | TP: {tp} | SL: {sl}")
				self.log("" + "—" * 60)
			else:
				# Compact single-line summary
				self.log(f" {time_str} Fib {self.fib_type or 'n/a'} {self.fib_target if self.fib_target is not None else 'n/a'} | Price {price:.2f} | Pos {pos} {dir_} TP {tp} SL {sl}")
			return

		# Default mode (keeps existing test expectations): session high/low retracements
		# Update high/low for fib calculation
		if self.last_high is None or price > self.last_high:
			self.last_high = price
		if self.last_low is None or price < self.last_low:
			self.last_low = price
		# Calculate Fibonacci retracement levels
		range_ = self.last_high - self.last_low if self.last_high and self.last_low else None
		if range_ and range_ > 0:
			self.fib_retracements = [round(self.last_high - range_ * level, 4) for level in self.fib_levels]
			self.log(f"{time_str} 🔢 Fib retracements: {self.fib_retracements}")
		if self.has_active_position():
			self._handle_active_position(time_str)
			return
		# Simple bounce/reject logic near fib level
		signal = None
		for fib in self.fib_retracements:
			if abs(price - fib) < self.TICK_SIZE * 2:
				if price > fib:
					signal = 'BUY'
				elif price < fib:
					signal = 'SELL'
				break
		if signal and signal != self.last_signal:
			self.log(f"{time_str} 🚦 Signal: {signal} at Fib {fib}")
			self.place_bracket_order(signal, self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
			self.last_signal = signal
		else:
			self.log(f"{time_str} 🔍 No valid signal")

	def reset_state(self):
		# Reset both modes' transient state
		self.last_signal = None
		self.last_high = None
		self.last_low = None
		self.fib_retracements = []
		self.fib_levels_prices = []
		self.fib_target = None
		self.fib_type = None
		self.active_direction = None
		self.active_stop_price = None
		self.active_tp_price = None
		self.trade_active = False
		self.last_stop_direction = None

	# Note: Bracket placement is centralized in base class.
