Module.register("MMM-FSS-LivePreview", {
    defaults: {
        previewFps: 10,
        timeoutAfterStable: 4000,
        maxWidth: 640,
        maxHeight: 480
    },
    FOOD_NAME_VI: {
        "apple": "Táo",
        "carrot": "Cà rốt",
        "egg": "Trứng",
        "lemon": "Chanh",
        "tomato": "Cà chua",
    },
    _(name) {
        return this.FOOD_NAME_VI[name] || name;
    },
    start() {
        this.isVisible = false;
        this.currentFrame = null;
        this.foods = "";
        this.currentEvents = [];
        this.pipelineTimeMs = 0;
        this.captureTimeMs = 0;
        this.motionTimeMs = 0;
        this.preprocessTimeMs = 0;
        this.inferenceTimeMs = 0;
        this.trackingTimeMs = 0;
        this.stableTimer = null;
        this.hideTimer = null;
        this.cameraState = "Waiting";
        this.sendSocketNotification("LIVE_PREVIEW_START", {});
    },
    getStyles() {
        return ["MMM-FSS-LivePreview.css"];
    },
    getDom() {
        const wrapper = document.createElement("div");
        wrapper.id = "fss-live-preview";
        wrapper.style.display = this.isVisible ? "block" : "none";

        const img = document.createElement("img");
        img.id = "fss-live-preview-img";
        img.style.maxWidth = this.config.maxWidth + "px";
        img.style.maxHeight = this.config.maxHeight + "px";
        wrapper.appendChild(img);

        // Food name overlay
        const foodLabel = document.createElement("div");
        foodLabel.id = "fss-lp-food-label";
        foodLabel.className = "fss-lp-food-label";
        foodLabel.textContent = this.foods ? this.foods.split(", ").map(f => this._(f)).join(", ") : "";
        wrapper.appendChild(foodLabel);

        // Notification text for checkin/checkout events
        const notifText = document.createElement("div");
        notifText.id = "fss-lp-notif";
        notifText.className = "fss-lp-notif";
        if (this.currentEvents.length > 0) {
            const lines = this.currentEvents.map(e => {
                const action = e.event === "added" ? "Thêm vào" : "Lấy ra";
                return action + " " + e.delta + " " + this._(e.food_name);
            });
            notifText.textContent = lines.join(" | ");
        } else {
            notifText.textContent = "";
        }
        wrapper.appendChild(notifText);

        // Pipeline step timing display
        if (this.pipelineTimeMs > 0) {
            const timeDisplay = document.createElement("div");
            timeDisplay.id = "fss-lp-time";
            timeDisplay.className = "fss-lp-time";
            timeDisplay.innerHTML =
                "⏱ " + this.pipelineTimeMs + "ms" +
                " &nbsp;|&nbsp; Capture " + this.captureTimeMs + "ms" +
                " &nbsp;|&nbsp; Motion " + this.motionTimeMs + "ms" +
                " &nbsp;|&nbsp; Pre " + this.preprocessTimeMs + "ms" +
                " &nbsp;|&nbsp; Infer " + this.inferenceTimeMs + "ms" +
                " &nbsp;|&nbsp; Track " + this.trackingTimeMs + "ms";
            wrapper.appendChild(timeDisplay);
        }

        // Camera status display
        const statusLine = document.createElement("div");
        statusLine.id = "fss-lp-status";
        statusLine.className = "fss-lp-status";
        statusLine.textContent = "📷 Camera: " + this.cameraState + ". Please put in the food";
        wrapper.appendChild(statusLine);

        return wrapper;
    },
    socketNotificationReceived(notification, payload) {
        if (notification === "LIVE_PREVIEW_FRAME") {
            this.cameraState = "Running";
            this.foods = payload.foods || "";
            this.currentEvents = payload.events || [];
            this.pipelineTimeMs = payload.pipelineTimeMs || 0;
            this.captureTimeMs = payload.captureTimeMs || 0;
            this.motionTimeMs = payload.motionTimeMs || 0;
            this.preprocessTimeMs = payload.preprocessTimeMs || 0;
            this.inferenceTimeMs = payload.inferenceTimeMs || 0;
            this.trackingTimeMs = payload.trackingTimeMs || 0;
            this.showPreview(payload.frame);
        } else if (notification === "LIVE_PREVIEW_DONE") {
            this.hidePreview();
        } else if (notification === "LIVE_PREVIEW_SHOW") {
            this.isVisible = true;
            this.updateDom();
        } else if (notification === "LIVE_PREVIEW_STATUS") {
            this.cameraState = payload.status || "Waiting";
            this.updateDom();
        }
    },
    showPreview(base64Frame) {
        this.isVisible = true;
        const img = document.getElementById("fss-live-preview-img");
        if (img) {
            img.src = "data:image/jpeg;base64," + base64Frame;
        }
        this.updateDom();
    },
    hidePreview() {
        this.isVisible = false;
        this.currentEvents = [];
        this.pipelineTimeMs = 0;
        this.captureTimeMs = 0;
        this.motionTimeMs = 0;
        this.preprocessTimeMs = 0;
        this.inferenceTimeMs = 0;
        this.trackingTimeMs = 0;
        this.cameraState = "Waiting";
        this.updateDom();
    }
});
