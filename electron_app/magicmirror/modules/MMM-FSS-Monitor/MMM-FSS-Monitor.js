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
		distanceThreshold: 0.6,      // meters (60cm)
		staleDataTimeout: 10000,     // ms before sensor data is considered stale
		blackScreenTimeout: 5000,    // ms to keep black screen visible after detection ends
		showDebugInfo: false,        // show distance/door state debug in corner
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
			isBlackScreenActive: false,
			distanceValue: null,
			distanceStale: false,
			doorState: null,
			doorOpen: false,
			lastDistanceUpdate: null,
			lastDoorUpdate: null,
		};

		// Timers
		this.blackScreenTimer = null;
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

		// Black screen overlay (initially hidden)
		const overlay = document.createElement("div");
		overlay.id = "fss-blackout-overlay";
		overlay.classList.add("fss-blackout-overlay");
		if (this.state.isBlackScreenActive) {
			overlay.classList.add("active");
		}
		wrapper.appendChild(overlay);

		// Door state indicator (always visible)
		const doorIndicator = document.createElement("div");
		doorIndicator.id = "fss-door-indicator";
		doorIndicator.classList.add("fss-door-indicator");

		if (this.state.doorState) {
			const isOpen = this.state.doorState === "OPEN";
			doorIndicator.textContent = isOpen ? "🚪 MỞ" : "🚪 ĐÓNG";
			doorIndicator.classList.toggle("door-open", isOpen);
			doorIndicator.classList.toggle("door-closed", !isOpen);
		} else {
			doorIndicator.textContent = "🚪 --";
			doorIndicator.classList.add("door-unknown");
		}
		wrapper.appendChild(doorIndicator);

		// Debug info (optional)
		if (this.config.showDebugInfo) {
			const debugInfo = document.createElement("div");
			debugInfo.classList.add("mmm-fss-monitor-debug");

			const distanceText = document.createElement("div");
			distanceText.textContent = `Distance: ${this.state.distanceValue !== null ? this.state.distanceValue.toFixed(2) : "N/A"} m`;
			debugInfo.appendChild(distanceText);

			const doorText = document.createElement("div");
			doorText.textContent = `Door: ${this.state.doorState || "N/A"}`;
			debugInfo.appendChild(doorText);

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

		if (notification === "DISTANCE_ALERT") {
			// Distance data: distance in meters, withinThreshold boolean
			this.state.distanceValue = payload.distance;
			this.state.lastDistanceUpdate = payload.timestamp || Date.now();
			this.state.distanceStale = false;

			Log.info(`MMM-FSS-Monitor: Distance alert - ${payload.distance.toFixed(2)}m (threshold: ${payload.withinThreshold})`);

			// Clear stale timer
			if (this.staleDistanceTimer) {
				clearTimeout(this.staleDistanceTimer);
			}
			this.staleDistanceTimer = setTimeout(() => {
				this.state.distanceStale = true;
				Log.warn("MMM-FSS-Monitor: Distance data is stale");
			}, this.config.staleDataTimeout);

			// Handle distance threshold crossing
			if (payload.withinThreshold && payload.distance < this.config.distanceThreshold) {
				// User detected - activate black screen
				this.activateBlackScreen();
			} else {
				// No user detected - deactivate black screen
				this.scheduleBlackScreenDeactivation();
			}

			this.updateDom();
		} else if (notification === "DOOR_STATE_UPDATE") {
			// Door state: state ("OPEN" or "CLOSED"), timestamp
			this.state.doorState = payload.state;
			this.state.lastDoorUpdate = payload.timestamp || Date.now();

			Log.info(`MMM-FSS-Monitor: Door state - ${payload.state}`);

			// Update door indicator element
			const doorIndicator = document.getElementById("fss-door-indicator");
			if (doorIndicator) {
				const isOpen = payload.state === "OPEN";
				doorIndicator.textContent = isOpen ? "🚪 MỞ" : "🚪 ĐÓNG";
				doorIndicator.classList.remove("door-open", "door-closed", "door-unknown");
				doorIndicator.classList.toggle("door-open", isOpen);
				doorIndicator.classList.toggle("door-closed", !isOpen);
			}

			// Clear stale timer
			if (this.staleDoorTimer) {
				clearTimeout(this.staleDoorTimer);
			}
			this.staleDoorTimer = setTimeout(() => {
				Log.warn("MMM-FSS-Monitor: Door state data is stale");
			}, this.config.staleDataTimeout);

			// Handle door open event - trigger camera signal (external system will handle)
			if (payload.state === "OPEN") {
				Log.info("MMM-FSS-Monitor: Door opened - camera system should be notified");
				this.sendSocketNotification("DOOR_OPENED_EVENT", { timestamp: payload.timestamp });
			}

			this.updateDom();
		} else if (notification === "MONITOR_ERROR") {
			Log.error(`MMM-FSS-Monitor: Error from node_helper - ${payload.error}`);
		}
	},

	/**
	 * Activate the black screen overlay.
	 * This is triggered when distance < threshold (user detected).
	 */
	activateBlackScreen() {
		if (this.state.isBlackScreenActive) {
			return; // Already active
		}

		Log.info("MMM-FSS-Monitor: Activating black screen");
		this.state.isBlackScreenActive = true;

		// Clear any pending deactivation
		if (this.blackScreenTimer) {
			clearTimeout(this.blackScreenTimer);
			this.blackScreenTimer = null;
		}

		this.updateDom();
	},

	/**
	 * Schedule deactivation of black screen.
	 * Waits for blackScreenTimeout before deactivating.
	 */
	scheduleBlackScreenDeactivation() {
		if (!this.state.isBlackScreenActive) {
			return; // Already inactive
		}

		// Clear any previous timer
		if (this.blackScreenTimer) {
			clearTimeout(this.blackScreenTimer);
		}

		Log.debug("MMM-FSS-Monitor: Scheduling black screen deactivation");
		this.blackScreenTimer = setTimeout(() => {
			Log.info("MMM-FSS-Monitor: Deactivating black screen");
			this.state.isBlackScreenActive = false;
			this.updateDom();
		}, this.config.blackScreenTimeout);
	},

	/**
	 * Stop the module and clean up timers.
	 */
	stop() {
		Log.info(`Stopping module: ${this.name}`);

		if (this.blackScreenTimer) {
			clearTimeout(this.blackScreenTimer);
		}
		if (this.staleDistanceTimer) {
			clearTimeout(this.staleDistanceTimer);
		}
		if (this.staleDoorTimer) {
			clearTimeout(this.staleDoorTimer);
		}
	},
});
