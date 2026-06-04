Module.register("MMM-FSS-Env", {
    defaults: {
        updateInterval: 2000,
        staleDataTimeout: 10000,
        temperatureFormat: "C",
        roundTemperature: false,
        roundHumidity: false,
        displayUnits: true,
    },

    getStyles() {
        return ["MMM-FSS-Env.css", "font-awesome.css"];
    },

    getScripts() {
        return ["moment.js"];
    },

    start() {
        this.sensorData = {
            sensor1: { temperature: 12.0, humidity: 60.0, timestamp: Date.now(), isStale: false },
            sensor2: { temperature: -1.0, humidity: 20.0, timestamp: Date.now(), isStale: false },
        };

        this.staleTimer1 = null;
        this.staleTimer2 = null;

        this.sendSocketNotification("MMM_FSS_ENV_START", {});
        setInterval(() => { this.updateDom(); }, this.config.updateInterval);
    },

    getDom() {
        const wrapper = document.createElement("div");
        wrapper.className = "fss-env-wrapper";

        const sensor1Box = this.createSensorBox("Ngăn trên", this.sensorData.sensor1);
        wrapper.appendChild(sensor1Box);

        const sensor2Box = this.createSensorBox("Ngăn dưới", this.sensorData.sensor2);
        wrapper.appendChild(sensor2Box);

        return wrapper;
    },

    createSensorBox(sensorLabel, data) {
        const box = document.createElement("div");
        box.className = "fss-panel fss-env-box";

        if (data.isStale) box.classList.add("stale");

        const label = document.createElement("div");
        label.className = "fss-panel-title-center fss-env-title";
        label.textContent = sensorLabel;
        box.appendChild(label);

        const dataRow = document.createElement("div");
        dataRow.className = "fss-env-data-row";

        // Nhiệt độ
        const tempCol = document.createElement("div");
        tempCol.className = "fss-env-data-item";
        
        const tempIcon = document.createElement("i");
        tempIcon.className = "fas fa-thermometer-half fss-env-icon-temp";
        tempCol.appendChild(tempIcon);

        const tempValue = document.createElement("span");
        if (data.temperature !== null) {
            const tempDisplay = this.config.roundTemperature ? Math.round(data.temperature) : data.temperature.toFixed(1);
            const unit = this.config.displayUnits ? `°${this.config.temperatureFormat}` : "";
            tempValue.textContent = `${tempDisplay}${unit}`;
        } else {
            tempValue.textContent = "-- °C";
        }
        tempCol.appendChild(tempValue);
        dataRow.appendChild(tempCol);

        // Độ ẩm
        const humidCol = document.createElement("div");
        humidCol.className = "fss-env-data-item";
        
        const humidIcon = document.createElement("i");
        humidIcon.className = "fas fa-droplet fss-env-icon-humid";
        humidCol.appendChild(humidIcon);

        const humidValue = document.createElement("span");
        if (data.humidity !== null) {
            const humidDisplay = this.config.roundHumidity ? Math.round(data.humidity) : data.humidity.toFixed(0);
            humidValue.textContent = this.config.displayUnits ? `${humidDisplay}%` : humidDisplay;
        } else {
            humidValue.textContent = "--%";
        }
        humidCol.appendChild(humidValue);
        dataRow.appendChild(humidCol);

        box.appendChild(dataRow);
        return box;
    },

    socketNotificationReceived(notification, payload) {
        if (notification === "ENVIRONMENT_UPDATE") {
            this.sensorData.sensor1.temperature = payload.temperature;
            this.sensorData.sensor1.humidity = payload.humidity;
            this.sensorData.sensor1.timestamp = payload.timestamp || Date.now();
            this.sensorData.sensor1.isStale = false;
            if (this.staleTimer1) clearTimeout(this.staleTimer1);
            this.staleTimer1 = setTimeout(() => {
                this.sensorData.sensor1.isStale = true;
                this.updateDom();
            }, this.config.staleDataTimeout);
            this.updateDom();
        } else if (notification === "SECONDARY_ENVIRONMENT_UPDATE") {
            this.sensorData.sensor2.temperature = payload.temperature;
            this.sensorData.sensor2.humidity = payload.humidity;
            this.sensorData.sensor2.timestamp = payload.timestamp || Date.now();
            this.sensorData.sensor2.isStale = false;
            if (this.staleTimer2) clearTimeout(this.staleTimer2);
            this.staleTimer2 = setTimeout(() => {
                this.sensorData.sensor2.isStale = true;
                this.updateDom();
            }, this.config.staleDataTimeout);
            this.updateDom();
        }
    }
});
