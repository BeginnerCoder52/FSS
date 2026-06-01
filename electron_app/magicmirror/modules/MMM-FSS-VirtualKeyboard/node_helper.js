const NodeHelper = require("node_helper");

module.exports = NodeHelper.create({
    start() {},
    socketNotificationReceived(notification, payload) {
        if (notification === "RECIPE_SEARCH") {
            this.sendSocketNotification("RECIPE_SEARCH", payload);
        }
    }
});
