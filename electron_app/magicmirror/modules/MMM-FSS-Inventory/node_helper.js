/**
 * @file node_helper.js for MMM-FSS-Inventory
 * @brief Backend handler for inventory module.
 *
 * Responsibilities:
 * - Start and manage the D-Bus listener (inventory_dbus_listener.py)
 * - Receive FRT detection results and inventory updates
 * - Relay data to frontend module via Socket.io
 * - Handle FRT_APP_ENABLED feature flag
 * - Handle errors and reconnection logic
 */

const NodeHelper = require("node_helper");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const SessionLog = require("../../../js/session_logger");
const { resolvePythonExecutable } = require("../fss_paths");

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
		this.frtAppEnabled = false;
	},

	/**
	 * Handle socket notifications from frontend module.
	 */
	socketNotificationReceived(notification, payload) {
		if (notification === "MMM_FSS_INVENTORY_START") {
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

		const pythonScriptPath = path.join(__dirname, "py_bridge", "inventory_dbus_listener.py");

		if (!fs.existsSync(pythonScriptPath)) {
			console.error(`${this.name}: Python script not found at ${pythonScriptPath}`);
			this.sendSocketNotification("INVENTORY_ERROR", {
				error: `Python script not found: ${pythonScriptPath}`,
			});
			return;
		}

		console.log(`${this.name}: Starting Python D-Bus listener from ${pythonScriptPath}`);

		try {
			const pythonExecutable = resolvePythonExecutable(__dirname);
			// Read FRT_APP_ENABLED flag from config or use default
			const frtAppEnabled = this.config?.frtAppEnabled ?? false;
			const args = [pythonScriptPath, frtAppEnabled.toString()];
			
			console.log(`${this.name}: FRT App enabled = ${frtAppEnabled}`);

			this.pythonProcess = spawn(pythonExecutable, args, {
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
			this.sendSocketNotification("INVENTORY_ERROR", {
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

			if (data.type === "FRT_UPDATE") {
				// FRT detection result
				console.log(`${this.name}: Relaying FRT update - ${data.quantity} ${data.className} (${data.action})`);
				this.sendSocketNotification("FRT_UPDATE", {
					foodId: data.foodId || `food_${Date.now()}`,
					className: data.className,
					quantity: data.quantity,
					imagePath: data.imagePath,
					action: data.action || "detected",
					timestamp: data.timestamp || Date.now(),
				});
				// Relay to MMM-FSS-Notification
				const actionLabel = data.action === "added" ? "to" : "from";
				this.sendSocketNotification("FSS_NOTIFICATION", {
					type: "food",
					message: `📦 ${data.action} ${data.quantity} ${data.className} ${actionLabel} the fridge`
				});
			} else if (data.type === "FRT_APP_ENABLED") {
				// FRT app enabled/disabled flag
				this.frtAppEnabled = data.enabled;
				console.log(`${this.name}: FRT App enabled = ${data.enabled}`);
				this.sendSocketNotification("FRT_APP_ENABLED_STATUS", {
					enabled: data.enabled,
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
			this.sendSocketNotification("INVENTORY_ERROR", {
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
		console.log(`${this.name}: Stopping node helper`);
		if (this.pythonProcess) {
			this.pythonProcess.kill();
			this.pythonProcess = null;
		}
	},
});
