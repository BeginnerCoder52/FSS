const NodeHelper = require("node_helper");
const { exec } = require("child_process");

module.exports = NodeHelper.create({
    start: function() {
        console.log("Starting node helper for: " + this.name);
    },

    socketNotificationReceived: function(notification, payload) {
        if (notification === "QUIT_MAGICMIRROR") {
            console.log("MMM-FSS-Quit received QUIT command. Stopping all FSS services.");
            exec("bash /home/richardmelvin52/FSS/FSS_RUN.sh --stop", (error, stdout, stderr) => {
                console.log("FSS_RUN.sh --stop output: ", stdout);
                if (error) console.error("Error stopping services: ", stderr);
                
                exec("pkill electron", () => {
                    process.exit(0);
                });
            });
        }
    }
});
