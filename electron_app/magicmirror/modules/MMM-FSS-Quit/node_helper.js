const NodeHelper = require("node_helper");

module.exports = NodeHelper.create({
    start: function() {
        console.log("Starting node helper for: " + this.name);
    },

    socketNotificationReceived: function(notification, payload) {
        if (notification === "QUIT_MAGICMIRROR") {
            console.log("MMM-FSS-Quit received QUIT command. Exiting process.");
            // Send SIGINT to gracefully close, or process.exit for immediate termination.
            // Using process.exit(0) effectively stops npm start / magicmirror completely.
            process.exit(0);
        }
    }
});
