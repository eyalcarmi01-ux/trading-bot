from algorithms.trading_algorithms_class import TradingAlgorithm
import math
import datetime
from statistics import stdev, mean
from collections import deque
import json

class CCI14_Compare_TradingAlgorithm(TradingAlgorithm):
	def __init__(self, contract_params, check_interval, initial_ema, ib=None, *, multi_ema_diagnostics=True, ema_spans=(10,20,32,50,100,200), multi_ema_bootstrap=True, bootstrap_lookback_bars=300, classic_cci=False, offline_seed_on_no_connection: bool = False, **kwargs):
		"""CCI14 compare strategy with optional multi-span EMA diagnostics & bootstrap.

		Parameters:
		- contract_params: dict for IB Future
		- check_interval: seconds between ticks
		- initial_ema: seed value when bootstrap unavailable
		- multi_ema_diagnostics (bool): enable multi-span diagnostics (default True)
		- ema_spans (tuple): spans to track (default legacy set)
		- multi_ema_bootstrap (bool): attempt historical bootstrap if connected
		- bootstrap_lookback_bars (int): approximate bars to request for seeding
		"""
		super().__init__(contract_params, ib=ib, **kwargs)
		self.CHECK_INTERVAL = check_interval
		self.EMA_FAST_PERIOD = 10
		self.EMA_SLOW_PERIOD = 200
		self.CCI_PERIOD = 14
		self.K_FAST = 2 / (self.EMA_FAST_PERIOD + 1)
		self.K_SLOW = 2 / (self.EMA_SLOW_PERIOD + 1)
		self.TICK_SIZE = 0.01
		self.SL_TICKS = 7
		self.TP_TICKS_LONG = 10
		self.TP_TICKS_SHORT = 10
		self.QUANTITY = 1
		self.price_history = []
		self.cci_values = []
		self.prev_cci = None
		self.ema_fast = initial_ema
		self.ema_slow = initial_ema
		self.paused_notice_shown = False
		self.signal_action = None
		self.signal_time = None
		# Multi-EMA diagnostics state
		self.multi_ema_enabled = multi_ema_diagnostics
		self.multi_ema_bootstrap = multi_ema_bootstrap
		self.bootstrap_lookback_bars = int(bootstrap_lookback_bars)
		self.multi_ema_spans = tuple(sorted(set(ema_spans)))
		# Initialize per-span EMAs & short histories for slope (last 10)
		self._multi_emas = {span: initial_ema for span in self.multi_ema_spans}
		self._multi_ema_histories = {span: deque(maxlen=10) for span in self.multi_ema_spans}
		for span in self.multi_ema_spans:
			self._multi_ema_histories[span].append(initial_ema)
		self._multi_ema_k = {span: 2/(span+1) for span in self.multi_ema_spans}
		self._multi_ema_bootstrapped = False
		# CCI mode toggle (False = current stdev-based; True = classic mean deviation)
		self.classic_cci_mode = bool(classic_cci)
		# When True, if IB is not connected we synthesize a minimal price history to enable immediate CCI/logging
		self.offline_seed_on_no_connection = bool(offline_seed_on_no_connection)
		# Ensure starting lifecycle phase in base is explicit
		try:
			self._set_trade_phase('IDLE', reason='Subclass init')
		except Exception:
			pass

	def calculate_and_log_cci(self, prices, time_str):
		if len(prices) < self.CCI_PERIOD:
			self.log(f"{time_str} ⚠️ Not enough data for CCI")
			return None
		typical_prices = prices[-self.CCI_PERIOD:]
		avg_tp = mean(typical_prices)
		if self.classic_cci_mode:
			# Classic mean-deviation based CCI
			mean_dev = sum(abs(p - avg_tp) for p in typical_prices) / self.CCI_PERIOD
			if mean_dev == 0:
				self.log(f"{time_str} ⚠️ Mean deviation zero — CCI = 0")
				cci = 0
			else:
				cci = (typical_prices[-1] - avg_tp) / (0.015 * mean_dev)
			dev_display = mean_dev
			dev_label = 'MeanDev'
		else:
			# Current implementation: sample standard deviation variant
			dev = stdev(typical_prices)
			if dev == 0:
				self.log(f"{time_str} ⚠️ StdDev is zero — CCI = 0")
				cci = 0
			else:
				cci = (typical_prices[-1] - avg_tp) / (0.015 * dev)
			dev_display = dev
			dev_label = 'StdDev'
		arrow = "🔼" if self.prev_cci is not None and cci > self.prev_cci else ("🔽" if self.prev_cci is not None and cci < self.prev_cci else "⏸️")
		mode = 'classic' if self.classic_cci_mode else 'stdev'
		self.log(f"{time_str} 📊 CCI14({mode}): {round(cci,2)} | Prev: {round(self.prev_cci,2) if self.prev_cci else '—'} {arrow} | Mean: {round(avg_tp,2)} | {dev_label}: {round(dev_display,2)}")
		# Legacy-format parity line (requested): concise labels CCI | Mean TP | Dev | Arrow
		try:
			self.log(f"{time_str} 📊 CCI: {round(cci,2)} | Mean TP: {round(avg_tp,2)} | Dev: {round(dev_display,2)} | Arrow: {arrow}")
		except Exception:
			pass
		self.prev_cci = cci
		return cci

	def on_tick(self, time_str):
		price = self.get_valid_price()
		if price is None:
			self.log(f"{time_str} ⚠️ Invalid price — skipping\n")
			return
		# Update multi-span EMAs (also sets ema_fast/ema_slow)
		self._update_multi_emas(price)
		# Core log of primary fast/slow EMAs
		self.log_price(time_str, price, EMA10=self.ema_fast, EMA200=self.ema_slow)
		# Optional multi-span diagnostics line
		self._maybe_log_multi_ema_diag(time_str)
		# Update price history and CCI
		self.update_price_history(price, maxlen=500)
		cci = None
		if len(self.price_history) >= self.CCI_PERIOD:
			cci = self.calculate_and_log_cci(self.price_history, time_str)
			if cci is not None:
				self.cci_values.append(cci)
				if len(self.cci_values) > 100:
					self.cci_values = self.cci_values[-100:]
		# Check for active position
		if self.has_active_position():
			self.log(f"{time_str} 🚫 BLOCKED: Trade already active\n")
			return
		# Signal detection
		if len(self.cci_values) >= 2 and self.signal_time is None:
			prev_cci = self.cci_values[-2]
			curr_cci = self.cci_values[-1]
			if prev_cci < 0 < curr_cci and price > self.ema_fast:
				self.signal_time = datetime.datetime.now()
				self.signal_action = 'BUY'
				self._set_trade_phase('SIGNAL_PENDING', reason='BUY CCI cross')
				self.log(f"{time_str} ⏳ BUY signal detected — waiting 3 minutes")
			elif prev_cci > 0 > curr_cci and price < self.ema_fast:
				self.signal_time = datetime.datetime.now()
				self.signal_action = 'SELL'
				self._set_trade_phase('SIGNAL_PENDING', reason='SELL CCI cross')
				self.log(f"{time_str} ⏳ SELL signal detected — waiting 3 minutes")
			else:
				self.log(f"{time_str} 🔍 No valid signal — conditions not met\n")
		# After 3 minutes, send bracket order
		if self.signal_time is not None:
			elapsed = (datetime.datetime.now() - self.signal_time).total_seconds()
			if elapsed >= 180:
				self.place_bracket_order(self.signal_action, self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				self.log(f"{time_str} ✅ Bracket sent — bot in active position\n")
				self.signal_time = None
				self.signal_action = None
			else:
				remaining = round(180 - elapsed)
				self.log(f"{time_str} ⏳ Waiting {remaining}s before sending bracket\n")

	def _update_multi_emas(self, price):
		if not self.multi_ema_enabled:
			# Maintain original fast/slow updates (compatibility) if diagnostics disabled
			self.ema_fast = self.calculate_ema(price, self.ema_fast, self.K_FAST)
			self.ema_slow = self.calculate_ema(price, self.ema_slow, self.K_SLOW)
			return
		try:
			for span in self.multi_ema_spans:
				prev = self._multi_emas.get(span)
				k = self._multi_ema_k[span]
				if prev is None:
					self._multi_emas[span] = price
				else:
					self._multi_emas[span] = round(price * k + prev * (1-k), 4)
				self._multi_ema_histories[span].append(self._multi_emas[span])
			# Sync primary fast/slow for compatibility
			self.ema_fast = self._multi_emas.get(self.EMA_FAST_PERIOD, self.ema_fast)
			self.ema_slow = self._multi_emas.get(self.EMA_SLOW_PERIOD, self.ema_slow)
		except Exception:
			# Fallback to original behavior on failure
			self.ema_fast = self.calculate_ema(price, self.ema_fast, self.K_FAST)
			self.ema_slow = self.calculate_ema(price, self.ema_slow, self.K_SLOW)

	def _maybe_log_multi_ema_diag(self, time_str):
		if not self.multi_ema_enabled:
			return
		try:
			parts = []
			for span in self.multi_ema_spans:
				val = self._multi_emas.get(span)
				parts.append(f"EMA{span}={val:.2f}" if isinstance(val,(int,float)) else f"EMA{span}=N/A")
			self.log(f"{time_str} 🧪 EMAS: " + " | ".join(parts))
		except Exception:
			pass

	def _bootstrap_multi_emas(self):
		if not (self.multi_ema_enabled and self.multi_ema_bootstrap):
			try:
				self.log("🧬 Bootstrap skipped (multi_ema_enabled or multi_ema_bootstrap disabled)")
			except Exception:
				pass
			return
		if self._multi_ema_bootstrapped:
			try:
				self.log("🧬 Bootstrap skipped (already bootstrapped)")
			except Exception:
				pass
			return
		ib_ref = getattr(self, 'ib', None)
		# Skip when mock (tests) or not connected
		try:
			if ib_ref is None:
				self.log("🧬 Bootstrap skipped (no IB instance)")
				return
			if hasattr(ib_ref, 'call_count'):
				self.log("🧬 Bootstrap skipped (mock IB detected)")
				return
			if not ib_ref.isConnected():
				self.log("🧬 Bootstrap skipped (not connected)")
				return
		except Exception:
			return
		try:
			# Request historical bars (1 min) enough to seed largest span
			self.log("🧬 Bootstrap requesting historical bars (2 D, 1 min) ...")
			bars = ib_ref.reqHistoricalData(self.contract, endDateTime='', durationStr='2 D', barSizeSetting='1 min', whatToShow='TRADES', useRTH=False, formatDate=1, keepUpToDate=False)
			closes = [b.close for b in bars if hasattr(b,'close')]
			try:
				first_ts = getattr(bars[0], 'date', 'n/a') if bars else 'n/a'
				last_ts = getattr(bars[-1], 'date', 'n/a') if bars else 'n/a'
				self.log(f"🧬 Bootstrap fetched bars={len(bars)} closes={len(closes)} range=[{first_ts} .. {last_ts}]")
			except Exception:
				pass
			if len(closes) < min(self.multi_ema_spans):
				self.log(f"🧬 Bootstrap aborted (need >= {min(self.multi_ema_spans)} closes, got {len(closes)})")
				return
			for span in self.multi_ema_spans:
				if len(closes) >= span:
					alpha = 2/(span+1)
					ema = closes[0]
					for p in closes[1:]:
						ema = p*alpha + ema*(1-alpha)
					self._multi_emas[span] = round(ema,4)
					self._multi_ema_histories[span].append(self._multi_emas[span])
					try:
						self.log(f"🧬 EMA{span} bootstrapped={self._multi_emas[span]}")
					except Exception:
						pass
			# Sync fast / slow
			self.ema_fast = self._multi_emas.get(self.EMA_FAST_PERIOD, self.ema_fast)
			self.ema_slow = self._multi_emas.get(self.EMA_SLOW_PERIOD, self.ema_slow)
			# Seed price history so CCI & trade condition logs appear on first tick (limit 500)
			try:
				if closes:
					prev_len = len(self.price_history)
					self.price_history = closes[-500:]
					self.log(f"🧪 Price history bootstrap seeded bars={len(self.price_history)} (previous={prev_len}) excerpt_last5={[round(c,2) for c in self.price_history[-5:]]}")
			except Exception:
				pass
			self._multi_ema_bootstrapped = True
			self.log(f"🧪 Multi-EMA bootstrap complete spans={self.multi_ema_spans} fast={self.ema_fast} slow={self.ema_slow}")
		except Exception as e:
			self.log(f"⚠️ Multi-EMA bootstrap failed: {e}")

	def pre_run(self):  # Hook invoked by base run()
		# Quick recent bar seeding so CCI & trade condition logs can appear on first tick.
		try:
			self._seed_recent_prices(minutes=14, bars_needed=self.CCI_PERIOD)
		except Exception:
			pass
		# Offline synthetic seeding (if enabled) when no connection & still insufficient history
		try:
			if self.offline_seed_on_no_connection and len(self.price_history) < self.CCI_PERIOD:
				ib_ref = getattr(self, 'ib', None)
				connected = False
				try:
					if ib_ref is not None and not hasattr(ib_ref, 'call_count') and ib_ref.isConnected():
						connected = True
				except Exception:
					connected = False
				if not connected:
					base = self.ema_fast if isinstance(self.ema_fast, (int,float)) else (self.ema_slow if isinstance(self.ema_slow,(int,float)) else 100.0)
					# Simple small random-ish walk using deterministic offsets (no random import needed for reproducibility)
					offsets = [0.00,0.02,-0.01,0.01,-0.02,0.03,-0.01,0.00,0.01,-0.02,0.02,-0.01,0.01,0.00]
					seed = [round(base + o, 2) for o in offsets[:self.CCI_PERIOD]]
					prev_len = len(self.price_history)
					self.price_history.extend(seed)
					if len(self.price_history) > 500:
						self.price_history = self.price_history[-500:]
					self.log(f"🧪 Offline synthetic seed injected count={len(seed)} prev_len={prev_len} history={len(self.price_history)} last5={[p for p in self.price_history[-5:]]}")
		except Exception:
			pass
		# Full multi-span EMA bootstrap (heavier) remains optional.
		try:
			self._bootstrap_multi_emas()
		except Exception:
			pass

	def _seed_recent_prices(self, *, minutes=14, bars_needed=14):
		"""Lightweight fetch of recent 1‑min bars (≈minutes) to seed price_history.
		Skips if already have enough prices or no live IB connection.
		"""
		if len(getattr(self, 'price_history', [])) >= bars_needed:
			try:
				self.log(f"🧪 Seed skipped (already have {len(self.price_history)} bars >= needed {bars_needed})")
			except Exception:
				pass
			return
		ib_ref = getattr(self, 'ib', None)
		try:
			if ib_ref is None:
				self.log("🧪 Seed skipped (no IB instance)")
				return
			if hasattr(ib_ref, 'call_count'):
				self.log("🧪 Seed skipped (mock IB)")
				return
			if not ib_ref.isConnected():
				self.log("🧪 Seed skipped (not connected)")
				return
		except Exception:
			return
		# Add buffer seconds to improve chance of getting >= bars_needed bars.
		seconds = max( (minutes * 60) + 120, bars_needed * 60 )
		duration = f"{seconds} S"
		try:
			self.log(f"🧪 Seed starting minutes={minutes} bars_needed={bars_needed} duration={duration}")
		except Exception:
			pass
		try:
			bars = ib_ref.reqHistoricalData(
				self.contract,
				endDateTime='',
				durationStr=duration,
				barSizeSetting='1 min',
				whatToShow='TRADES',
				useRTH=False,
				formatDate=1,
				keepUpToDate=False,
			)
			closes = [b.close for b in bars if hasattr(b, 'close')]
			if not closes:
				self.log("🧪 Seed aborted (no closes returned)")
				return
			seed = closes[-bars_needed:]
			prev_len = len(self.price_history)
			self.price_history.extend(seed)
			if len(self.price_history) > 500:
				self.price_history = self.price_history[-500:]
			try:
				self.log(f"🧪 Seed loaded count={len(seed)} prev_len={prev_len} new_history={len(self.price_history)} last_seed_vals={[round(x,2) for x in seed[-5:]]}")
			except Exception:
				pass
		except Exception as e:
			self.log(f"⚠️ Recent seed fetch failed: {e}")

	def reset_state(self):
		self.price_history = []
		self.cci_values = []
		self.prev_cci = None
		self.ema_fast = None
		self.ema_slow = None
		self.signal_action = None
		self.signal_time = None
