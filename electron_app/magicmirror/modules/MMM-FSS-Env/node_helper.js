/**
 * @file node_helper.js for MMM-FSS-Env
 * @brief Backend handler for environmental sensor module.
 * 
 * Responsibilities:
 * - Start and manage the D-Bus listener (env_dbus_listener.py)
 * - Receive environment data from D-Bus signals
 * - Relay data to frontend module via Socket.io
 * - Handle errors and reconnection logic
 * 
 * Communication flow:
 * D-Bus signals → env_dbus_listener.py → Socket.io → node_helper → frontend module
 */

const NodeHelper = require("node_helper");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const SessionLog = require("../../js/session_logger");
const { resolvePythonExecutable } = require("../fss_paths");

module.exports = NodeHelper.create({
	/**
	 * Start the node helper.
	 * Initialize Python D-Bus listener process.
	 */
	start() {
		console.log(`${this.name}: Starting node helper`);
		SessionLog.info(`[${this.name}] Node helper started`);
		this.pythonProcess = null;
		this.isListening = false;
		this.reconnectAttempts = 0;
		this.maxReconnectAttempts = 10;
		this.reconnectDelay = 1000; // ms, will increase exponentially
	},

	/**
	 * Handle socket notifications from frontend module.
	 * Triggered when module requests to start D-Bus listener.
	 */
	socketNotificationReceived(notification, payload) {
		if (notification === "MMM_FSS_ENV_START") {
			console.log(`${this.name}: Received start notification`);
			this.startDBusListener();
		}
	},

	/**
	 * Start the Python D-Bus listener process.
	 * The listener connects to DBDaemon and relays sensor data.
	 */
	startDBusListener() {
		if (this.pythonProcess) {
			console.warn(`${this.name}: Python process already running`);
			return;
		}

		const pythonScriptPath = path.join(__dirname, "py_bridge", "env_dbus_listener.py");

		// Check if Python script exists
		if (!fs.existsSync(pythonScriptPath)) {
			console.error(`${this.name}: Python script not found at ${pythonScriptPath}`);
			this.sendSocketNotification("ENV_ERROR", {
				error: `Python script not found: ${pythonScriptPath}`,
			});
			return;
		}

		console.log(`${this.name}: Starting Python D-Bus listener from ${pythonScriptPath}`);

		try {
			// Spawn Python process to listen to D-Bus signals
			const pythonExecutable = resolvePythonExecutable(__dirname);
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

			this.pythonProcess.on("error", (err) => {
				console.error(`${this.name}: Process error - ${err.message}`);
				this.sendSocketNotification("ENV_ERROR", {
					error: `Process error: ${err.message}`,
				});
				this.pythonProcess = null;
				this.isListening = false;
				this.attemptReconnect();
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
			this.sendSocketNotification("ENV_ERROR", {
				error: `Failed to start Python process: ${error.message}`,
			});
			this.attemptReconnect();
		}
	},

	/**
	 * Handle output from Python D-Bus listener.
	 * Parse JSON data and relay to frontend.
	 * 
	 * @param {string} message - Raw message from Python process
	 */
	handlePythonOutput(message) {
		try {
			// Try to parse as JSON
			const data = JSON.parse(message);

			if (data.type === "ENVIRONMENT_UPDATE") {
				// Sensor 1 data
				console.log(`${this.name}: Relaying Sensor 1 update - Temp: ${data.temperature}°C, Humidity: ${data.humidity}%`);
				this.sendSocketNotification("ENVIRONMENT_UPDATE", {
					temperature: data.temperature,
					humidity: data.humidity,
					timestamp: data.timestamp || Date.now(),
				});
			} else if (data.type === "SECONDARY_ENVIRONMENT_UPDATE") {
				// Sensor 2 data
				console.log(`${this.name}: Relaying Sensor 2 update - Temp: ${data.temperature}°C, Humidity: ${data.humidity}%`);
				this.sendSocketNotification("SECONDARY_ENVIRONMENT_UPDATE", {
					temperature: data.temperature,
					humidity: data.humidity,
					timestamp: data.timestamp || Date.now(),
				});
			} else if (data.type === "STATUS") {
				console.log(`${this.name}: Status - ${data.message}`);
			} else {
				console.warn(`${this.name}: Unknown message type - ${data.type}`);
			}
		} catch (error) {
			// If not JSON, log as plain text
			console.debug(`${this.name}: Plain text message - ${message}`);
		}
	},

	/**
	 * Attempt to reconnect to D-Bus listener with exponential backoff.
	 * Maximum reconnect attempts: 10
	 * Initial delay: 1s, max delay: 30s
	 */
	attemptReconnect() {
		if (this.reconnectAttempts >= this.maxReconnectAttempts) {
			console.error(`${this.name}: Max reconnect attempts reached`);
			this.sendSocketNotification("ENV_ERROR", {
				error: "Failed to reconnect to D-Bus listener after maximum attempts",
			});
			return;
		}

		this.reconnectAttempts++;
		const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);

		console.log(`${this.name}: Attempting reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

		setTimeout(() => {
			this.startDBusListener();
		}, delay);
	},

	/**
	 * Stop the Python process when module is stopped.
	 */
	stop() {
		SessionLog.info(`[${this.name}] Node helper stopped`);
		console.log(`${this.name}: Stopping node helper`);
		if (this.pythonProcess) {
			this.pythonProcess.kill("SIGTERM");
			setTimeout(() => {
				if (this.pythonProcess && !this.pythonProcess.killed) {
					this.pythonProcess.kill("SIGKILL");
				}
			}, 3000);
		}
		this.pythonProcess = null;
	},
});
