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
        
        // Dữ liệu mẫu (mock) để demo UI dựa theo thiết kế
        if (Object.keys(this.inventoryData.foods).length === 0) {
            this.inventoryData.foods = {
                "mock1": { name: "Cà rốt", quantity: 2, imagePath: "" },
                "mock2": { name: "Cà chua", quantity: 2, imagePath: "" },
                "mock3": { name: "Chanh", quantity: 2, imagePath: "" },
                "mock4": { name: "Táo", quantity: 2, imagePath: "" },
                "mock5": { name: "Vải", quantity: 2, imagePath: "" },
                "mock6": { name: "Xoài", quantity: 2, imagePath: "" },
                "mock7": { name: "Sữa", quantity: 2, imagePath: "" },
                "mock8": { name: "Trứng", quantity: 2, imagePath: "" },
                "mock9": { name: "Trà sữa", quantity: 2, imagePath: "" },
                "mock10": { name: "Coca", quantity: 2, imagePath: "" },
                "mock11": { name: "Nước lọc", quantity: 2, imagePath: "" },
                "mock12": { name: "Sữa chua", quantity: 2, imagePath: "" }
            };
        }

        this.staleTimer = null;
        this.sendSocketNotification("MMM_FSS_INVENTORY_START", {});
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
        if (foodKeys.length === 0) {
            const emptyMsg = document.createElement("div");
            emptyMsg.textContent = "Không có nguyên liệu";
            grid.appendChild(emptyMsg);
        } else {
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
            this.sendNotification("FSS_NOTIFICATION", {
                type: action === "removed" ? "food_removed" : "food_added",
                message: `Bạn vừa ${action === "removed" ? "lấy ra" : "thêm vào"} x${payload.quantity} ${payload.className}`
            });

            if (action === "added" || action === "updated") {
                this.inventoryData.foods[foodId] = {
                    name: payload.className,
                    quantity: payload.quantity,
                    imagePath: payload.imagePath,
                    timestamp: payload.timestamp || Date.now(),
                };
            } else if (action === "removed") {
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
