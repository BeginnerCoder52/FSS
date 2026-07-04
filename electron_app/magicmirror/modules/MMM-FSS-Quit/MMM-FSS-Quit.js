Module.register("MMM-FSS-Quit", {
    defaults: {
        text: "Thoát"
    },
    
    getStyles: function() {
        return ["MMM-FSS-Quit.css"];
    },

    start: function() {
        this.showConfirm = false;
    },

    getDom: function() {
        var wrapper = document.createElement("div");
        wrapper.className = "fss-quit-wrapper";

        if (this.showConfirm) {
            var confirmText = document.createElement("div");
            confirmText.innerHTML = "Bạn có chắc muốn thoát?";
            confirmText.className = "fss-quit-confirm-text";
            wrapper.appendChild(confirmText);

            var btnContainer = document.createElement("div");
            btnContainer.className = "fss-quit-btn-container";

            var yesBtn = document.createElement("button");
            yesBtn.innerHTML = "Có (Yes)";
            yesBtn.className = "fss-quit-btn fss-quit-yes";
            yesBtn.style.pointerEvents = "auto";
            yesBtn.onclick = () => {
                wrapper.innerHTML = `<div style="text-align: center; font-size: 1.2em; color: #ff4444; padding: 10px;">
                    <i class="fas fa-spinner fa-spin"></i> Quit signals received. Shutting down...
                </div>`;
                this.sendSocketNotification("QUIT_MAGICMIRROR", {});
            };
            yesBtn.addEventListener("touchend", (e) => {
                e.preventDefault();
                yesBtn.onclick();
            });
            btnContainer.appendChild(yesBtn);

            var noBtn = document.createElement("button");
            noBtn.innerHTML = "Không (No)";
            noBtn.className = "fss-quit-btn fss-quit-no";
            noBtn.style.pointerEvents = "auto";
            noBtn.onclick = () => {
                this.showConfirm = false;
                this.updateDom();
            };
            noBtn.addEventListener("touchend", (e) => {
                e.preventDefault();
                noBtn.onclick();
            });
            btnContainer.appendChild(noBtn);

            wrapper.appendChild(btnContainer);
        } else {
            var quitBtn = document.createElement("button");
            quitBtn.innerHTML = '<i class="fa fa-power-off"></i> ' + this.config.text;
            quitBtn.className = "fss-quit-main-btn";
            quitBtn.style.pointerEvents = "auto";
            quitBtn.onclick = () => {
                this.showConfirm = true;
                this.updateDom();
            };
            quitBtn.addEventListener("touchend", (e) => {
                e.preventDefault();
                quitBtn.onclick();
            });
            wrapper.appendChild(quitBtn);
        }

        return wrapper;
    }
});
