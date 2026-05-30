Module.register("MMM-FSS-Notification", {
    defaults: {
        displayDuration: 5000,
        maxVisible: 5,
        animationDuration: 300
    },
    start() {
        this.notifications = [];
    },
    getDom() {
        const wrapper = document.createElement("div");
        wrapper.id = "fss-notification-overlay";

        this.notifications.forEach((n) => {
            const card = document.createElement("div");
            card.className = `fss-notification-card fss-notif-${n.type}`;

            const msg = document.createElement("div");
            msg.className = "fss-notif-message";
            msg.textContent = n.message;
            card.appendChild(msg);

            const timer = document.createElement("div");
            timer.className = "fss-notif-timer";
            card.appendChild(timer);

            wrapper.appendChild(card);
        });

        return wrapper;
    },
    socketNotificationReceived(notification, payload) {
        if (notification === "FSS_NOTIFICATION") {
            this.playNotificationSound(payload.type);
            this.addNotification(payload);
        }
    },
    addNotification(data) {
        this.notifications.unshift({
            id: Date.now(),
            type: data.type,
            message: data.message,
            timestamp: Date.now()
        });

        if (this.notifications.length > this.config.maxVisible) {
            this.notifications.pop();
        }

        this.updateDom();

        setTimeout(() => {
            this.notifications = this.notifications.filter(n => n.id !== data.id);
            this.updateDom();
        }, this.config.displayDuration);
    },
    playNotificationSound(type) {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const soundMap = {
                "user_detected":  { freq: 440, dur: 200, count: 3, gap: 80 },
                "door_open":      { freq: 660, dur: 150, count: 2, gap: 100 },
                "door_closed":    { freq: 330, dur: 150, count: 1, gap: 0 },
                "food_added":     { freq: 880, dur: 100, count: 1, gap: 0 },
                "food_removed":   { freq: 330, dur: 200, count: 2, gap: 150 },
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
        } catch(e) {
            // Audio not available
        }
    }
});
