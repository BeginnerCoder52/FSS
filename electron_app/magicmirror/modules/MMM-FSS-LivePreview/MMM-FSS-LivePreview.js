Module.register("MMM-FSS-LivePreview", {
    defaults: {
        previewFps: 10,
        timeoutAfterStable: 3000,
        maxWidth: 640,
        maxHeight: 480
    },
    start() {
        this.isVisible = false;
        this.currentFrame = null;
        this.stableTimer = null;
        this.sendSocketNotification("LIVE_PREVIEW_START", {});
    },
    getDom() {
        const wrapper = document.createElement("div");
        wrapper.id = "fss-live-preview";
        wrapper.style.display = this.isVisible ? "block" : "none";

        const video = document.createElement("img");
        video.id = "fss-live-preview-img";
        video.style.maxWidth = this.config.maxWidth + "px";
        video.style.maxHeight = this.config.maxHeight + "px";
        wrapper.appendChild(video);

        return wrapper;
    },
    socketNotificationReceived(notification, payload) {
        if (notification === "LIVE_PREVIEW_FRAME") {
            this.showPreview(payload.frame);
        } else if (notification === "LIVE_PREVIEW_DONE") {
            this.hidePreview();
        } else if (notification === "LIVE_PREVIEW_SHOW") {
            this.isVisible = true;
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

        if (this.stableTimer) clearTimeout(this.stableTimer);
        this.stableTimer = setTimeout(() => {
            this.hidePreview();
        }, this.config.timeoutAfterStable);
    },
    hidePreview() {
        this.isVisible = false;
        this.updateDom();
    }
});
