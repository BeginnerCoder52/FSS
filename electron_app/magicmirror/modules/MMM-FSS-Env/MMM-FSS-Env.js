/**
 * @file MMM-FSS-Env.js
 * @brief MagicMirror module for displaying dual SHT3x environmental sensor readings.
 * 
 * Displays temperature and humidity from two SHT3x sensors:
 * - Sensor 1 (Ngan mat): Top section
 * - Sensor 2 (Ngan dong): Bottom section
 * 
 * Each sensor displays temperature with thermometer icon and humidity with water droplet icon.
 * Updates in real-time via Socket.io notifications from the D-Bus listener.
 * 
 * Position: right_center
 * Theme: Dark theme with light text and icons
 */

Module.register("MMM-FSS-Env", {
	/**
	 * Default module configuration.
	 * These can be overridden in the MagicMirror config.js
	 */
	defaults: {
		updateInterval: 2000,        // ms between expected sensor updates
		staleDataTimeout: 10000,     // ms before data is considered stale
		temperatureFormat: "C",      // C for Celsius, F for Fahrenheit
		roundTemperature: true,      // round temperature to integer
		roundHumidity: true,         // round humidity to integer
		displayUnits: true,          // show °C or °F and % symbols
	},

	/**
	 * Get required stylesheets.
	 */
	getStyles() {
		return ["MMM-FSS-Env.css", "font-awesome.css"];
	},

	/**
	 * Get required scripts.
	 */
	getScripts() {
		return ["moment.js"];
	},

	/**
	 * Define module start.
	 * Initialize data structure and notify node_helper to start listening.
	 */
	start() {
		Log.info(`Starting module: ${this.name}`);

		// Initialize sensor data structure
		this.sensorData = {
			sensor1: {
				temperature: null,
				humidity: null,
				timestamp: null,
				isStale: false,
			},
			sensor2: {
				temperature: null,
				humidity: null,
				timestamp: null,
				isStale: false,
			},
		};

		// Initialize stale data timers
		this.staleTimer1 = null;
		this.staleTimer2 = null;

		// Notify node_helper to start D-Bus listener
		this.sendSocketNotification("MMM_FSS_ENV_START", {});
		Log.info("MMM-FSS-Env: Notified node_helper to start D-Bus listener");

		// Set update interval for UI refresh
		setInterval(() => {
			this.updateDom();
		}, this.config.updateInterval);
	},

	/**
	 * Generate the DOM for the module.
	 * Displays two sensor boxes with temperature, humidity, and icons.
	 */
	getDom() {
		const wrapper = document.createElement("div");
		wrapper.classList.add("mmm-fss-env-container");

		// Sensor 1 (Ngan mat) - Top Box
		const sensor1Box = this.createSensorBox("Ngan mat (Sensor 1)", this.sensorData.sensor1);
		wrapper.appendChild(sensor1Box);

		// Separator
		const separator = document.createElement("div");
		separator.classList.add("mmm-fss-env-separator");
		wrapper.appendChild(separator);

		// Sensor 2 (Ngan dong) - Bottom Box
		const sensor2Box = this.createSensorBox("Ngan dong (Sensor 2)", this.sensorData.sensor2);
		wrapper.appendChild(sensor2Box);

		return wrapper;
	},

	/**
	 * Create a sensor display box with temperature and humidity.
	 * 
	 * @param {string} sensorLabel - Label for the sensor (e.g., "Ngan mat")
	 * @param {Object} data - Sensor data object {temperature, humidity, isStale}
	 * @returns {HTMLElement} - DOM element for the sensor box
	 */
	createSensorBox(sensorLabel, data) {
		const box = document.createElement("div");
		box.classList.add("mmm-fss-env-sensor-box");

		if (data.isStale) {
			box.classList.add("stale");
		}

		// Sensor label
		const label = document.createElement("div");
		label.classList.add("mmm-fss-env-label");
		label.textContent = sensorLabel;
		box.appendChild(label);

		// Temperature row
		const tempRow = document.createElement("div");
		tempRow.classList.add("mmm-fss-env-row");

		const tempIcon = document.createElement("i");
		tempIcon.classList.add("fas", "fa-thermometer-half", "mmm-fss-env-icon");
		tempRow.appendChild(tempIcon);

		const tempValue = document.createElement("span");
		tempValue.classList.add("mmm-fss-env-value");
		if (data.temperature !== null) {
			const tempDisplay = this.config.roundTemperature ? Math.round(data.temperature) : data.temperature.toFixed(1);
			const unit = this.config.displayUnits ? `°${this.config.temperatureFormat}` : "";
			tempValue.textContent = `${tempDisplay}${unit}`;
		} else {
			tempValue.textContent = "-- °C";
			tempValue.classList.add("no-data");
		}
		tempRow.appendChild(tempValue);

		box.appendChild(tempRow);

		// Humidity row
		const humidRow = document.createElement("div");
		humidRow.classList.add("mmm-fss-env-row");

		const humidIcon = document.createElement("i");
		humidIcon.classList.add("fas", "fa-droplet", "mmm-fss-env-icon");
		humidRow.appendChild(humidIcon);

		const humidValue = document.createElement("span");
		humidValue.classList.add("mmm-fss-env-value");
		if (data.humidity !== null) {
			const humidDisplay = this.config.roundHumidity ? Math.round(data.humidity) : data.humidity.toFixed(1);
			humidValue.textContent = this.config.displayUnits ? `${humidDisplay}%` : humidDisplay;
		} else {
			humidValue.textContent = "--%";
			humidValue.classList.add("no-data");
		}
		humidRow.appendChild(humidValue);

		box.appendChild(humidRow);

		return box;
	},

	/**
	 * Handle Socket.io notifications from node_helper.
	 * Receives environment data updates and refresh DOM.
	 * 
	 * @param {string} notification - Notification name
	 * @param {Object} payload - Notification payload
	 */
	socketNotificationReceived(notification, payload) {
		Log.debug(`MMM-FSS-Env received: ${notification}`, payload);

		if (notification === "ENVIRONMENT_UPDATE") {
			// Update Sensor 1 data
			this.sensorData.sensor1.temperature = payload.temperature;
			this.sensorData.sensor1.humidity = payload.humidity;
			this.sensorData.sensor1.timestamp = payload.timestamp || Date.now();
			this.sensorData.sensor1.isStale = false;

			// Clear stale timer for Sensor 1
			if (this.staleTimer1) {
				clearTimeout(this.staleTimer1);
			}
			// Set stale timer for Sensor 1
			this.staleTimer1 = setTimeout(() => {
				this.sensorData.sensor1.isStale = true;
				Log.warn("MMM-FSS-Env: Sensor 1 data is stale");
				this.updateDom();
			}, this.config.staleDataTimeout);

			Log.info(`MMM-FSS-Env: Sensor 1 updated - Temp: ${payload.temperature}°C, Humidity: ${payload.humidity}%`);
			this.updateDom();
		} else if (notification === "SECONDARY_ENVIRONMENT_UPDATE") {
			// Update Sensor 2 data
			this.sensorData.sensor2.temperature = payload.temperature;
			this.sensorData.sensor2.humidity = payload.humidity;
			this.sensorData.sensor2.timestamp = payload.timestamp || Date.now();
			this.sensorData.sensor2.isStale = false;

			// Clear stale timer for Sensor 2
			if (this.staleTimer2) {
				clearTimeout(this.staleTimer2);
			}
			// Set stale timer for Sensor 2
			this.staleTimer2 = setTimeout(() => {
				this.sensorData.sensor2.isStale = true;
				Log.warn("MMM-FSS-Env: Sensor 2 data is stale");
				this.updateDom();
			}, this.config.staleDataTimeout);

			Log.info(`MMM-FSS-Env: Sensor 2 updated - Temp: ${payload.temperature}°C, Humidity: ${payload.humidity}%`);
			this.updateDom();
		} else if (notification === "ENV_ERROR") {
			Log.error(`MMM-FSS-Env: Error from node_helper - ${payload.error}`);
		}
	},
});
