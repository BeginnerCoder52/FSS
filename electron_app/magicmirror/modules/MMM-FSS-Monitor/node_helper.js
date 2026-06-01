/**
 * @file node_helper.js for MMM-FSS-Monitor
 * @brief Backend handler for monitor module (distance and door sensors).
 *
 * Responsibilities:
 * - Start and manage the D-Bus listener (monitor_dbus_listener.py)
 * - Receive distance and door state data from D-Bus signals
 * - Relay data to frontend module via Socket.io
 * - Handle errors and reconnection logic
 */

const NodeHelper = require("node_helper");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const SessionLog = require("../../../js/session_logger");

module.exports = NodeHelper.create({
	/**
	 * Start the node helper.
	 */
	start() {
		console.log(`${this.name}: Starting node helper`);
		SessionLog.info(`[${this.name}] Node helper started`);
		this.pythonProcess = null;
		this.isListening = false;
		this.reconnectAttempts = 0;
		this.maxReconnectAttempts = 10;
		this.reconnectDelay = 1000; // ms
	},

	/**
	 * Handle socket notifications from frontend module.
	 */
	socketNotificationReceived(notification, payload) {
		if (notification === "MMM_FSS_MONITOR_START") {
			console.log(`${this.name}: Received start notification`);
			this.startDBusListener();
		}
	},

	/**
	 * Start the Python D-Bus listener process.
	 */
	startDBusListener() {
		if (this.pythonProcess) {
			console.warn(`${this.name}: Python process already running`);
			return;
		}

		const pythonScriptPath = path.join(__dirname, "py_bridge", "monitor_dbus_listener.py");

		if (!fs.existsSync(pythonScriptPath)) {
			console.error(`${this.name}: Python script not found at ${pythonScriptPath}`);
			this.sendSocketNotification("MONITOR_ERROR", {
				error: `Python script not found: ${pythonScriptPath}`,
			});
			return;
		}

		console.log(`${this.name}: Starting Python D-Bus listener from ${pythonScriptPath}`);

		try {
			const pythonExecutable = "/home/richardmelvin52/FSS/.venv/bin/python3";
			this.pythonProcess = spawn(pythonExecutable, [pythonScriptPath], {
				stdio: ["pipe", "pipe", "pipe"],
				detached: false,
			});

			this.pythonProcess.stdout.on("data", (data) => {
				const message = data.toString().trim();
				console.log(`${this.name} [PY]: ${message}`);
				this.handlePythonOutput(message);
			});

			this.pythonProcess.stderr.on("data", (data) => {
				const error = data.toString().trim();
				console.error(`${this.name} [PY ERROR]: ${error}`);
			});

			this.pythonProcess.on("close", (code) => {
				console.warn(`${this.name}: Python process exited with code ${code}`);
				this.pythonProcess = null;
				this.isListening = false;
				this.attemptReconnect();
			});

			this.isListening = true;
			this.reconnectAttempts = 0;
		} catch (error) {
			console.error(`${this.name}: Failed to start Python process - ${error.message}`);
			this.sendSocketNotification("MONITOR_ERROR", {
				error: `Failed to start Python process: ${error.message}`,
			});
			this.attemptReconnect();
		}
	},

	/**
	 * Handle output from Python D-Bus listener.
	 *
	 * @param {string} message - Raw message from Python process
	 */
	handlePythonOutput(message) {
		try {
			const data = JSON.parse(message);

			if (data.type === "DISTANCE_ALERT") {
				console.log(
					`${this.name}: Relaying distance alert - ${data.distance.toFixed(2)}m, within threshold: ${data.withinThreshold}`
				);
				this.sendSocketNotification("DISTANCE_ALERT", {
					distance: data.distance,
					withinThreshold: data.withinThreshold,
					timestamp: data.timestamp || Date.now(),
				});
			} else if (data.type === "DOOR_STATE_UPDATE") {
				const doorState = data.state || data.doorState || "UNKNOWN";
				console.log(`${this.name}: Relaying door state - ${doorState}`);
				this.sendSocketNotification("DOOR_STATE_UPDATE", {
					state: doorState,
					timestamp: data.timestamp || Date.now(),
				});
				// Relay to MMM-FSS-Notification
				this.sendSocketNotification("FSS_NOTIFICATION", {
					type: "monitor",
					message: `🚪 DOOR ${data.state} - Opening/Turning off USB Camera…`
				});
			} else if (data.type === "STATUS") {
				console.log(`${this.name}: Status - ${data.message}`);
			} else {
				console.warn(`${this.name}: Unknown message type - ${data.type}`);
			}
		} catch (error) {
			console.debug(`${this.name}: Plain text message - ${message}`);
		}
	},

	/**
	 * Attempt to reconnect with exponential backoff.
	 */
	attemptReconnect() {
		if (this.reconnectAttempts >= this.maxReconnectAttempts) {
			console.error(`${this.name}: Max reconnect attempts reached`);
			this.sendSocketNotification("MONITOR_ERROR", {
				error: "Failed to reconnect to D-Bus listener after maximum attempts",
			});
			return;
		}

		this.reconnectAttempts++;
		const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);

		console.log(
			`${this.name}: Attempting reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
		);

		setTimeout(() => {
			this.startDBusListener();
		}, delay);
	},

	/**
	 * Stop the module.
	 */
	stop() {
		SessionLog.info(`[${this.name}] Node helper stopped`);
		console.log(`${this.name}: Stopping node helper`);
		if (this.pythonProcess) {
			this.pythonProcess.kill();
			this.pythonProcess = null;
		}
	},
});
