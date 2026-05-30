/**
 * @file MMM-FSS-Inventory.js
 * @brief MagicMirror module for FRT detection results and food inventory display.
 *
 * This module has two visual components:
 * 1. **Notification Submodule** (center): Shows detection events as notifications
 *    - Format: "{quantity} {class_name} has added/removed"
 *    - Displays detected food image above message
 *    - Auto-dismisses after 3 seconds
 *    - FRT_APP_ENABLED flag: shows "FRTApp not available" when disabled
 *
 * 2. **Inventory Submodule** (bottom_center): Shows current food inventory
 *    - Grid of food items with images
 *    - Quantity displayed next to each food
 *    - Updates in real-time as inventory changes
 *
 * Positions: Notifications at 'center', Inventory at 'bottom_center'
 * Theme: Dark theme with light text and icons
 */

Module.register("MMM-FSS-Inventory", {
	/**
	 * Default module configuration.
	 */
	defaults: {
		notificationDuration: 3000,  // ms before notification auto-dismisses
		notificationQueueMax: 10,    // max notifications to queue
		updateInterval: 1000,        // ms between UI refresh
		staleDataTimeout: 15000,     // ms before inventory data considered stale
		frtAppEnabled: true,         // whether FRTApp is available
		showPlaceholder: false,      // show "FRTApp not available" when disabled
	},

	/**
	 * Get required stylesheets.
	 */
	getStyles() {
		return ["MMM-FSS-Inventory.css", "font-awesome.css"];
	},

	/**
	 * Get required scripts.
	 */
	getScripts() {
		return ["moment.js"];
	},

	/**
	 * Define module start.
	 */
	start() {
		Log.info(`Starting module: ${this.name}`);

		// Initialize notification queue
		this.notificationQueue = [];

		// Initialize inventory data
		this.inventoryData = {
			foods: {},  // { food_id: { name, quantity, imagePath, timestamp } }
			lastUpdate: null,
			isStale: false,
		};

		// Timers
		this.staleTimer = null;

		// Notify node_helper to start listener
		this.sendSocketNotification("MMM_FSS_INVENTORY_START", {});
		Log.info("MMM-FSS-Inventory: Notified node_helper to start D-Bus listener");

		// Refresh UI periodically
		setInterval(() => {
			this.updateDom();
		}, this.config.updateInterval);
	},

	/**
	 * Generate the DOM for the module.
	 * Creates both notification and inventory display sections.
	 */
	getDom() {
		const wrapper = document.createElement("div");
		wrapper.classList.add("mmm-fss-inventory-container");

		// Add notification section
		const notificationSection = this.createNotificationSection();
		wrapper.appendChild(notificationSection);

		// Add inventory section
		const inventorySection = this.createInventorySection();
		wrapper.appendChild(inventorySection);

		return wrapper;
	},

	/**
	 * Create the notification display section.
	 * Shows current notification (if any) from queue.
	 *
	 * @returns {HTMLElement} - DOM element for notification section
	 */
	createNotificationSection() {
		const section = document.createElement("div");
		section.classList.add("mmm-fss-inventory-notification-section");

		if (!this.config.frtAppEnabled) {
			if (this.config.showPlaceholder) {
				const placeholder = document.createElement("div");
				placeholder.classList.add("mmm-fss-inventory-placeholder");
				placeholder.innerHTML =
					'<i class="fas fa-cube"></i><p>FRTApp not available</p><small>Waiting for detection service...</small>';
				section.appendChild(placeholder);
			}
			return section;
		}

		// If there's a notification, display it
		if (this.notificationQueue.length > 0) {
			const notification = this.notificationQueue[0];
			const notificationBox = document.createElement("div");
			notificationBox.classList.add("mmm-fss-inventory-notification");

			// Display detected image (if available)
			if (notification.imagePath) {
				const imageContainer = document.createElement("div");
				imageContainer.classList.add("mmm-fss-inventory-notification-image");
				const img = document.createElement("img");
				img.src = notification.imagePath;
				img.alt = notification.className;
				imageContainer.appendChild(img);
				notificationBox.appendChild(imageContainer);
			}

			// Display message
			const message = document.createElement("div");
			message.classList.add("mmm-fss-inventory-notification-message");
			message.innerHTML = `<strong>${notification.quantity} ${notification.className}</strong><br><small>${notification.action}</small>`;
			notificationBox.appendChild(message);

			section.appendChild(notificationBox);
		}

		return section;
	},

	/**
	 * Create the inventory display section.
	 * Shows grid of current foods with quantities.
	 *
	 * @returns {HTMLElement} - DOM element for inventory section
	 */
	createInventorySection() {
		const section = document.createElement("div");
		section.classList.add("mmm-fss-inventory-section");

		// Inventory title
		const title = document.createElement("div");
		title.classList.add("mmm-fss-inventory-title");
		title.textContent = "INVENTORY";
		section.appendChild(title);

		// Inventory grid
		const grid = document.createElement("div");
		grid.classList.add("mmm-fss-inventory-grid");

		if (this.inventoryData.isStale) {
		grid.classList.add("stale");
		}

		const foodKeys = Object.keys(this.inventoryData.foods);
		if (foodKeys.length === 0) {
			// No foods in inventory
			const emptyMsg = document.createElement("div");
			emptyMsg.classList.add("mmm-fss-inventory-empty");
			emptyMsg.textContent = "No foods detected";
			grid.appendChild(emptyMsg);
		} else {
			// Sort items by last_updated descending
			const sorted = foodKeys
				.map(k => ({ key: k, food: this.inventoryData.foods[k] }))
				.sort((a, b) => (b.food.timestamp || 0) - (a.food.timestamp || 0));

			// Display each food item
			for (const { key: foodId, food } of sorted) {
				const foodItem = document.createElement("div");
				foodItem.classList.add("mmm-fss-inventory-item");

				// Food thumbnail
				if (food.imagePath) {
					const img = document.createElement("img");
					img.src = food.imagePath;
					img.alt = food.name;
					foodItem.appendChild(img);
				}

				// Food name
				const name = document.createElement("div");
				name.classList.add("item-name");
				name.textContent = food.name;
				foodItem.appendChild(name);

				// Food quantity
				const qty = document.createElement("div");
				qty.classList.add("item-qty");
				qty.textContent = `x${food.quantity}`;
				foodItem.appendChild(qty);

				grid.appendChild(foodItem);
			}
		}

		section.appendChild(grid);

		return section;
	},

	/**
	 * Handle socket notifications from node_helper.
	 *
	 * @param {string} notification - Notification name
	 * @param {Object} payload - Notification payload
	 */
	socketNotificationReceived(notification, payload) {
		Log.debug(`MMM-FSS-Inventory received: ${notification}`, payload);

		if (notification === "FRT_UPDATE") {
			// FRT detection result
			const foodId = payload.foodId || `unknown_${Date.now()}`;
			const className = payload.className;
			const quantity = payload.quantity;
			const imagePath = payload.imagePath;
			const action = payload.action || "detected"; // "added" or "removed"

			Log.info(`MMM-FSS-Inventory: FRT Update - ${quantity} ${className} (${action})`);

			// Update inventory
			if (action === "added" || action === "updated") {
				this.inventoryData.foods[foodId] = {
					name: className,
					quantity: quantity,
					imagePath: imagePath,
					timestamp: payload.timestamp || Date.now(),
				};
			} else if (action === "removed") {
				delete this.inventoryData.foods[foodId];
			}

			// Add to notification queue
			this.addNotification({
				foodId: foodId,
				quantity: quantity,
				className: className,
				imagePath: imagePath,
				action: `${action}`,
				timestamp: payload.timestamp || Date.now(),
			});

			// Clear stale timer
			if (this.staleTimer) {
				clearTimeout(this.staleTimer);
			}
			this.inventoryData.isStale = false;

			// Set stale timer
			this.staleTimer = setTimeout(() => {
				this.inventoryData.isStale = true;
				Log.warn("MMM-FSS-Inventory: Inventory data is stale");
				this.updateDom();
			}, this.config.staleDataTimeout);

			this.updateDom();
		} else if (notification === "INVENTORY_UPDATE") {
			// Full inventory update
			Log.info("MMM-FSS-Inventory: Full inventory update received");
			this.inventoryData.foods = payload.foods || {};
			this.inventoryData.lastUpdate = payload.timestamp || Date.now();
			this.inventoryData.isStale = false;

			// Clear stale timer
			if (this.staleTimer) {
				clearTimeout(this.staleTimer);
			}

			// Set stale timer
			this.staleTimer = setTimeout(() => {
				this.inventoryData.isStale = true;
				Log.warn("MMM-FSS-Inventory: Inventory data is stale");
				this.updateDom();
			}, this.config.staleDataTimeout);

			this.updateDom();
		} else if (notification === "FRT_APP_ENABLED_STATUS") {
			// FRT app enabled/disabled status
			this.config.frtAppEnabled = payload.enabled;
			Log.info(`MMM-FSS-Inventory: FRT App enabled status = ${payload.enabled}`);
			this.updateDom();
		} else if (notification === "INVENTORY_ERROR") {
			Log.error(`MMM-FSS-Inventory: Error from node_helper - ${payload.error}`);
		}
	},

	/**
	 * Add a notification to the queue and auto-dismiss.
	 *
	 * @param {Object} notification - Notification object
	 */
	addNotification(notification) {
		if (this.notificationQueue.length >= this.config.notificationQueueMax) {
			this.notificationQueue.shift(); // Remove oldest
		}

		this.notificationQueue.push(notification);

		// Auto-dismiss after duration
		setTimeout(() => {
			if (this.notificationQueue.length > 0 && this.notificationQueue[0] === notification) {
				this.notificationQueue.shift();
				this.updateDom();
			}
		}, this.config.notificationDuration);
	},

	/**
	 * Stop the module and clean up timers.
	 */
	stop() {
		Log.info(`Stopping module: ${this.name}`);
		if (this.staleTimer) {
			clearTimeout(this.staleTimer);
		}
	},
});
