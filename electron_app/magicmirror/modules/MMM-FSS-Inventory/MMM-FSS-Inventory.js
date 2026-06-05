Module.register("MMM-FSS-Inventory", {
    defaults: {
        updateInterval: 1000,
        staleDataTimeout: 15000,
        frtAppEnabled: true,
        showPlaceholder: false,
    },

    getStyles() {
        return ["MMM-FSS-Inventory.css"];
    },

    getScripts() {
        return ["moment.js"];
    },

    start() {
        Log.info(`Starting module: ${this.name}`);
        this.inventoryData = {
            foods: {},
            lastUpdate: null,
            isStale: false,
        };

        // Dữ liệu sẽ được nạp từ D-Bus/DB thay vì dữ liệu mẫu.

        this.staleTimer = null;
        this.sendSocketNotification("MMM_FSS_INVENTORY_START", this.config);
        setInterval(() => {
            this.updateDom();
        }, this.config.updateInterval);
    },

    getDom() {
        const wrapper = document.createElement("div");
        wrapper.className = "fss-panel fss-inventory-panel";

        const title = document.createElement("div");
        title.className = "fss-panel-title-center";
        title.textContent = "NGUYÊN LIỆU TỒN KHO";
        title.style.fontWeight = "bold";
        title.style.textAlign = "center";
        title.style.fontSize = "1.5em";
        title.style.marginBottom = "1.2em";
        wrapper.appendChild(title);

        const grid = document.createElement("div");
        grid.className = "fss-inventory-grid";

        if (!this.config.frtAppEnabled && this.config.showPlaceholder) {
            const emptyMsg = document.createElement("div");
            emptyMsg.textContent = "FRTApp not available";
            grid.appendChild(emptyMsg);
            wrapper.appendChild(grid);
            return wrapper;
        }

        const foodKeys = Object.keys(this.inventoryData.foods);
        if (foodKeys.length > 0) {
            const sorted = foodKeys
                .map(k => ({ key: k, food: this.inventoryData.foods[k] }))
                .sort((a, b) => (b.food.timestamp || 0) - (a.food.timestamp || 0));

            for (const { key: foodId, food } of sorted) {
                const itemWrapper = document.createElement("div");
                itemWrapper.className = "fss-inventory-item-wrapper";

                const circleAvatar = document.createElement("div");
                circleAvatar.className = "fss-inventory-circle";

                if (food.imagePath) {
                    const img = document.createElement("img");
                    img.src = food.imagePath;
                    img.alt = food.name;
                    circleAvatar.appendChild(img);
                } else {
                    const defaultIcon = document.createElement("div");
                    defaultIcon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:50%;height:50%;color:var(--color-text-dimmed)"><path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"></path><line x1="3" y1="6" x2="21" y2="6"></line><path d="M16 10a4 4 0 0 1-8 0"></path></svg>`;
                    defaultIcon.style.display = "flex";
                    defaultIcon.style.alignItems = "center";
                    defaultIcon.style.justifyContent = "center";
                    defaultIcon.style.width = "100%";
                    defaultIcon.style.height = "100%";
                    circleAvatar.appendChild(defaultIcon);
                }

                itemWrapper.appendChild(circleAvatar);

                const labelWrapper = document.createElement("div");
                labelWrapper.className = "fss-inventory-label";

                const nameSpan = document.createElement("span");
                nameSpan.className = "fss-inventory-name";
                nameSpan.textContent = food.name;

                const qtySpan = document.createElement("span");
                qtySpan.className = "fss-inventory-qty";
                qtySpan.textContent = `x${food.quantity}`;

                labelWrapper.appendChild(nameSpan);
                labelWrapper.appendChild(document.createTextNode(" "));
                labelWrapper.appendChild(qtySpan);

                itemWrapper.appendChild(labelWrapper);
                grid.appendChild(itemWrapper);
            }
        }

        wrapper.appendChild(grid);
        return wrapper;
    },

    socketNotificationReceived(notification, payload) {
        if (notification === "FRT_UPDATE") {
            const foodId = payload.foodId || `unknown_${Date.now()}`;
            const action = payload.action || "detected";

            // Forward event to Notification module for showing popup box
            if (payload.source !== "database") {
                this.sendNotification("FSS_NOTIFICATION", {
                    type: action === "removed" ? "food_removed" : "food_added",
                    message: `Bạn vừa ${action === "removed" ? "lấy ra" : "thêm vào"} x${payload.delta || payload.quantity} ${payload.className}`
                });
            }

            if (payload.quantity > 0) {
                this.inventoryData.foods[foodId] = {
                    name: payload.className,
                    quantity: payload.quantity,
                    imagePath: payload.imagePath,
                    timestamp: payload.timestamp || Date.now(),
                };
            } else {
                delete this.inventoryData.foods[foodId];
            }

            this.resetStaleTimer();
            this.updateDom();
        } else if (notification === "INVENTORY_UPDATE") {
            this.inventoryData.foods = payload.foods || {};
            this.inventoryData.lastUpdate = payload.timestamp || Date.now();
            this.inventoryData.isStale = false;
            this.resetStaleTimer();
            this.updateDom();
        } else if (notification === "FRT_APP_ENABLED_STATUS") {
            this.config.frtAppEnabled = payload.enabled;
            this.updateDom();
        }
    },

    resetStaleTimer() {
        if (this.staleTimer) clearTimeout(this.staleTimer);
        this.inventoryData.isStale = false;
        this.staleTimer = setTimeout(() => {
            this.inventoryData.isStale = true;
            this.updateDom();
        }, this.config.staleDataTimeout);
    },

    stop() {
        if (this.staleTimer) clearTimeout(this.staleTimer);
    }
});
