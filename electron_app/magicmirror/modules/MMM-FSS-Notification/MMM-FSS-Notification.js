Module.register("MMM-FSS-Notification", {
    defaults: {
        displayDuration: 5000,
        maxVisible: 15,
        animationDuration: 300,
        showMockNotifications: false
    },
    getStyles() {
        return ["MMM-FSS-Notification.css"];
    },
    start() {
        this.notifications = [];
        this.audioCtx = null;
        this.audioReady = false;

        // Mock data removed. Notifications will be populated by D-Bus signals.
    },
    getScripts() {
        return [];
    },
    getDom() {
        const wrapper = document.createElement("div");
        wrapper.className = "fss-panel fss-notification-panel";

        const titleBox = document.createElement("div");
        titleBox.className = "fss-notif-title-horizontal";
        titleBox.innerHTML = "THÔNG BÁO";
        titleBox.style.fontWeight = "bold";
        titleBox.style.textAlign = "center";
        titleBox.style.fontSize = "1.5em";
        titleBox.style.marginRight = "1.2em";

        const listWrapper = document.createElement("div");
        listWrapper.className = "fss-notif-list-wrapper";

        this.notifications.forEach((n) => {
            const row = document.createElement("div");
            row.className = "fss-list-row-full";

            const circle = document.createElement("div");
            circle.className = "fss-circle-check";
            row.appendChild(circle);

            const msg = document.createElement("span");
            msg.textContent = n.message;
            row.appendChild(msg);

            listWrapper.appendChild(row);
        });

        // The mockup has the text "THÔNG BÁO" written vertically on the left side, 
        // and the list of notifications on the right.
        const flexContainer = document.createElement("div");
        flexContainer.style.display = "flex";
        flexContainer.style.flexDirection = "row";

        flexContainer.appendChild(titleBox);
        flexContainer.appendChild(listWrapper);

        wrapper.appendChild(flexContainer);

        return wrapper;
    },
    notificationReceived(notification, payload, sender) {
        if (notification === "FSS_NOTIFICATION") {
            this.playNotificationSound(payload.type);
            this.addNotification(payload);
        }
    },
    addNotification(data, preventTimeout = false) {
        this.notifications.unshift({
            id: Date.now() + Math.random(),
            type: data.type,
            message: data.message,
            timestamp: Date.now()
        });

        if (this.notifications.length > this.config.maxVisible) {
            this.notifications.pop();
        }

        this.updateDom();
    },
    initAudio() {
        if (this.audioReady) return;
        try {
            if (!this.audioCtx) {
                this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (this.audioCtx.state === "suspended") {
                this.audioCtx.resume().then(() => {
                    this.audioReady = true;
                }).catch(() => { });
            } else {
                this.audioReady = true;
            }
        } catch (e) { }
    },

    playNotificationSound(type) {
        this.initAudio();
        if (!this.audioReady && (!this.audioCtx || this.audioCtx.state !== "running")) {
            return;
        }
        try {
            const ctx = this.audioCtx;
            const soundMap = {
                "user_detected": { freq: 440, dur: 200, count: 3, gap: 80 },
                "door_open": { freq: 660, dur: 150, count: 2, gap: 100 },
                "door_closed": { freq: 330, dur: 150, count: 1, gap: 0 },
                "food_added": { freq: 880, dur: 100, count: 1, gap: 0 },
                "food_removed": { freq: 330, dur: 200, count: 2, gap: 150 },
                "recommend_done": { freq: 550, dur: 150, count: 2, gap: 100, freq2: 770 }
            };

            const s = soundMap[type] || { freq: 500, dur: 100, count: 1, gap: 0 };

            let startTime = ctx.currentTime;
            for (let i = 0; i < s.count; i++) {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);

                osc.frequency.value = s.freq2 && i === 1 ? s.freq2 : s.freq;
                osc.type = "sine";

                gain.gain.setValueAtTime(0.3, startTime);
                gain.gain.exponentialRampToValueAtTime(0.001, startTime + s.dur / 1000);

                osc.start(startTime);
                osc.stop(startTime + s.dur / 1000);
                startTime += (s.dur + s.gap) / 1000;
            }
        } catch (e) {
            // Audio not available
        }
    }
});
