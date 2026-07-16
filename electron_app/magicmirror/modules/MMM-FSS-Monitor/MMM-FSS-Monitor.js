/**
 * @file MMM-FSS-Monitor.js
 * @brief MagicMirror module for monitoring distance and door sensors.
 *
 * Functions:
 * - If distance < 60cm: Show full-screen black overlay (user presence detected)
 * - If door opens: Log event for external camera system to handle
 *
 * This module handles screen control to give users privacy when detected.
 * The overlay is CSS-based and covers the entire screen.
 *
 * Position: top_bar (can be hidden, acts as background control)
 * Theme: Dark, minimal UI (most interaction is via CSS overlay)
 */

Module.register("MMM-FSS-Monitor", {
	/**
	 * Default module configuration.
	 */
	defaults: {
		distanceThreshold: 60,      // centimeters
		staleDataTimeout: 10000,     // ms before sensor data is considered stale
		showDebugInfo: false,        // show distance/door state debug in corner
		ignoreDistanceSensor: false, // ignore distance sensor errors
		ignoreDoorSensor: false,     // ignore door sensor
		disableBlackout: false,      // disable blackout for debugging
	},

	/**
	 * Get required stylesheets.
	 */
	getStyles() {
		return ["MMM-FSS-Monitor.css"];
	},

	/**
	 * Define module start.
	 */
	start() {
		Log.info(`Starting module: ${this.name}`);

		// Initialize state
		this.state = {
			isUserPresenceDetected: false,
			distanceValue: null,
			distanceStale: false,
			doorState: null,
			doorOpen: false,
			lastDistanceUpdate: null,
			lastDoorUpdate: null,
		};

		// Timers
		this.staleDistanceTimer = null;
		this.staleDoorTimer = null;

		// Notify node_helper to start listener
		this.sendSocketNotification("MMM_FSS_MONITOR_START", {});
		Log.info("MMM-FSS-Monitor: Notified node_helper to start D-Bus listener");
	},

	/**
	 * Generate the DOM for the module.
	 * Main purpose is hidden, but we create a container for the overlay.
	 */
	getDom() {
		const wrapper = document.createElement("div");
		wrapper.classList.add("mmm-fss-monitor-container");

		// Blackout overlay
		let overlay = document.getElementById("fss-blackout-overlay");
		if (!overlay) {
			overlay = document.createElement("div");
			overlay.id = "fss-blackout-overlay";
			document.body.appendChild(overlay);
		}
		
		if (this.state.isUserPresenceDetected && !this.config.disableBlackout) {
			overlay.classList.add("active");
		} else {
			overlay.classList.remove("active");
		}

		// Door state + distance indicator (always visible)
		const doorIndicator = document.createElement("div");
		doorIndicator.id = "fss-door-indicator";
		doorIndicator.classList.add("fss-door-indicator");

		let doorText = "🚪 --";
		if (this.state.doorState) {
			const isOpen = this.state.doorState === "DOOR_OPEN";
			doorText = isOpen ? "🚪 MỞ" : "🚪 ĐÓNG";
			doorIndicator.classList.toggle("door-open", isOpen);
			doorIndicator.classList.toggle("door-closed", !isOpen);
		} else {
			doorIndicator.classList.add("door-unknown");
		}

		let distText = "";
		if (this.state.distanceValue !== null) {
			distText = " 📏 " + this.state.distanceValue.toFixed(0) + "cm";
		}
		doorIndicator.textContent = doorText + distText;
		wrapper.appendChild(doorIndicator);

		// Debug info (optional)
		if (this.config.showDebugInfo) {
			const debugInfo = document.createElement("div");
			debugInfo.classList.add("mmm-fss-monitor-debug");

			const distanceText = document.createElement("div");
			distanceText.textContent = `Distance: ${this.state.distanceValue !== null ? this.state.distanceValue.toFixed(0) : "N/A"} cm`;
			debugInfo.appendChild(distanceText);

			const doorText = document.createElement("div");
			doorText.textContent = `Door: ${this.state.doorState || "N/A"}`;
			debugInfo.appendChild(doorText);

			const presenceText = document.createElement("div");
			presenceText.textContent = `Presence: ${this.state.isUserPresenceDetected ? "Yes" : "No"}`;
			debugInfo.appendChild(presenceText);

			wrapper.appendChild(debugInfo);
		}

		return wrapper;
	},

	/**
	 * Handle socket notifications from node_helper.
	 *
	 * @param {string} notification - Notification name
	 * @param {Object} payload - Notification payload
	 */
	socketNotificationReceived(notification, payload) {
		Log.debug(`MMM-FSS-Monitor received: ${notification}`, payload);

		if (notification === "FSS_NOTIFICATION") {
			// Forward to all modules via MagicMirror internal notification
			this.sendNotification("FSS_NOTIFICATION", payload);
			return;
		}

        if (notification === "USER_PRESENCE") {
			// User presence detection
			this.state.isUserPresenceDetected = payload.presence;
			Log.info(`MMM-FSS-Monitor: User presence detected - ${payload.presence}`);
			this.updateDom();
			return;
		} else if (notification === "DISTANCE_ALERT") {
			if (this.config.ignoreDistanceSensor) {
				Log.debug("MMM-FSS-Monitor: Distance sensor ignored by config");
				return;
			}
			// Distance data: distance in cm, withinThreshold boolean
			this.state.distanceValue = payload.distance;
			this.state.lastDistanceUpdate = payload.timestamp || Date.now();
			this.state.distanceStale = false;
			
			// Debounce presence state to prevent flickering from sensor noise (819.10cm spikes)
			if (payload.withinThreshold) {
				this.state.isUserPresenceDetected = true;
				if (this.presenceTimeout) {
					clearTimeout(this.presenceTimeout);
					this.presenceTimeout = null;
				}
			} else {
				// Only set to false if it stays false for 1.5 seconds
				if (!this.presenceTimeout && this.state.isUserPresenceDetected) {
					this.presenceTimeout = setTimeout(() => {
						this.state.isUserPresenceDetected = false;
						this.presenceTimeout = null;
						this.updateDom();
					}, 1500);
				} else if (!this.state.isUserPresenceDetected) {
					this.state.isUserPresenceDetected = false;
				}
			}

			Log.info(`MMM-FSS-Monitor: Distance alert - ${payload.distance.toFixed(2)}cm (threshold: ${payload.withinThreshold})`);

			// Clear stale timer
			if (this.staleDistanceTimer) {
				clearTimeout(this.staleDistanceTimer);
			}
			this.staleDistanceTimer = setTimeout(() => {
				this.state.distanceStale = true;
				Log.warn("MMM-FSS-Monitor: Distance data is stale");
			}, this.config.staleDataTimeout);

			this.updateDom();
		} else if (notification === "DOOR_STATE_UPDATE") {
			if (this.config.ignoreDoorSensor) {
				Log.debug("MMM-FSS-Monitor: Door sensor ignored by config");
				return;
			}
			// Door state: state ("OPEN" or "CLOSED"), timestamp
			this.state.doorState = payload.state;
			this.state.lastDoorUpdate = payload.timestamp || Date.now();

			Log.info(`MMM-FSS-Monitor: Door state - ${payload.state}`);

			// Clear stale timer
			if (this.staleDoorTimer) {
				clearTimeout(this.staleDoorTimer);
			}
			this.staleDoorTimer = setTimeout(() => {
				Log.warn("MMM-FSS-Monitor: Door state data is stale");
			}, this.config.staleDataTimeout);

			this.updateDom();
		} else if (notification === "MONITOR_ERROR") {
			Log.error(`MMM-FSS-Monitor: Error from node_helper - ${payload.error}`);
		}
	},

	/**
	 * Stop the module and clean up timers.
	 */
	stop() {
		Log.info(`Stopping module: ${this.name}`);

		if (this.staleDistanceTimer) {
			clearTimeout(this.staleDistanceTimer);
		}
		if (this.staleDoorTimer) {
			clearTimeout(this.staleDoorTimer);
		}
		if (this.presenceTimeout) {
			clearTimeout(this.presenceTimeout);
		}
	},
});
