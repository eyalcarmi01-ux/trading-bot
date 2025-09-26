"""Removed. Use algorithms.cci14_120_trading_algorithm instead."""
raise ImportError("cci14rev_trading_algorithm removed. Import CCI14_120_TradingAlgorithm from cci14_120_trading_algorithm")
				cci_display = f"{self._ANSI_RED}{round(cci,2)}{self._ANSI_RESET}"
			elif cci <= -120:
				cci_display = f"{self._ANSI_GREEN}{round(cci,2)}{self._ANSI_RESET}"
		dir_fragment = f" | Dir: {self.active_direction}" if self.active_direction else ""
		self.log(f"{time_str} 📊 CCI14: {cci_display} | Prev: {round(self.prev_cci,2) if self.prev_cci is not None else '—'} {arrow} | Mean: {round(avg_tp,2)} | StdDev: {round(dev,2)}{dir_fragment}")
		self.prev_cci = cci
		return cci

	def check_long_condition(self):
		v = self.cci_values
		return len(v) >= 3 and v[-3] < -120 and v[-2] > -120 and v[-1] > v[-2]

	def check_short_condition(self):
		v = self.cci_values
		return len(v) >= 3 and v[-3] >= 120 and v[-2] < 120 and v[-1] < v[-2]

	def on_tick(self, time_str):
		self.on_tick_common(time_str)
		price = self.get_valid_price()
		if price is None:
			self.log(f"{time_str} ⚠️ Invalid price — skipping (EMAs preserved)\n")
			return
		# Update price history
		self.update_price_history(price, maxlen=500)
		# Calculate and log EMA10 using base class utility
		if len(self.price_history) >= self.EMA_FAST_PERIOD:
			last_price = self.price_history[-1]
			# Initialize fast EMA if needed, then update with latest price
			if self.ema_fast is None:
				self.ema_fast = last_price
			self.ema_fast = self.calculate_ema(last_price, self.ema_fast, self.K_FAST)
			self.log_price(time_str, price, EMA10=self.ema_fast)
		# Update EMA200 using base class utility
		if self.ema_slow is not None:
			self.ema_slow = self.calculate_ema(price, self.ema_slow, self.K_SLOW)
		else:
			self.ema_slow = price
		# Calculate CCI
		cci = None
		if len(self.price_history) >= self.CCI_PERIOD:
			cci = self.calculate_and_log_cci(self.price_history, time_str)
			if cci is not None:
				self.cci_values.append(cci)
				if len(self.cci_values) > 100:
					self.cci_values = self.cci_values[-100:]
		# Check for active position
		if self.has_active_position():
			# Invoke base position handler to enable manual SL breach monitoring & fill scanning
			self.handle_active_position(time_str)
			# If handler closed position (manual SL or fill) clear direction
			if (not self.has_active_position()) and self.active_direction and self.current_sl_price is None:
				self.active_direction = None
			return
		# Signal detection
		long_signal = self.check_long_condition()
		short_signal = self.check_short_condition()
		ema_filter_long = self.ema_fast is not None and self.ema_slow is not None and self.ema_fast > self.ema_slow
		ema_filter_short = self.ema_fast is not None and self.ema_slow is not None and self.ema_fast < self.ema_slow
		if long_signal:
			if ema_filter_long:
				self.log(f"{time_str} ⏳ LONG signal (CCI) + EMA10>EMA200 confirmed — sending bracket order")
				prev_entry = self._last_entry_id
				self.place_bracket_order('BUY', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				# Detect if new entry order appeared; track direction
				if self._last_entry_id != prev_entry and self._last_entry_id is not None:
					self.active_direction = 'LONG'
					self.log(f"{time_str} ✅ LONG trade opened (EMA10 {round(self.ema_fast,4)} > EMA200 {round(self.ema_slow,4)})")
			else:
				self.log(f"{time_str} 🔁 LONG CCI pattern but EMA10<=EMA200 — filtered out")
		elif short_signal:
			if ema_filter_short:
				self.log(f"{time_str} ⏳ SHORT signal (CCI) + EMA10<EMA200 confirmed — sending bracket order")
				prev_entry = self._last_entry_id
				self.place_bracket_order('SELL', self.QUANTITY, self.TICK_SIZE, self.SL_TICKS, self.TP_TICKS_LONG, self.TP_TICKS_SHORT)
				if self._last_entry_id != prev_entry and self._last_entry_id is not None:
					self.active_direction = 'SHORT'
					self.log(f"{time_str} ✅ SHORT trade opened (EMA10 {round(self.ema_fast,4)} < EMA200 {round(self.ema_slow,4)})")
			else:
				self.log(f"{time_str} 🔁 SHORT CCI pattern but EMA10>=EMA200 — filtered out")
		else:
			self.log(f"{time_str} 🔍 No valid signal — conditions not met\n")

	def reset_state(self):
		self.price_history = []
		self.cci_values = []
		self.prev_cci = None
		self.ema_fast = None
		self.active_direction = None
