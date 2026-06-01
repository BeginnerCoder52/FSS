/* Config Sample
 *
 * For more information on how you can configure this file
 * see https://docs.magicmirror.builders/configuration/introduction.html
 * and https://docs.magicmirror.builders/modules/configuration.html
 *
 * You can use environment variables using a `config.js.template` file instead of `config.js`
 * which will be converted to `config.js` while starting. For more information
 * see https://docs.magicmirror.builders/configuration/introduction.html#enviromnent-variables
 */
let config = {
	address: "localhost",	// Address to listen on, can be:
							// - "localhost", "127.0.0.1", "::1" to listen on loopback interface
							// - another specific IPv4/6 to listen on a specific interface
							// - "0.0.0.0", "::" to listen on any interface
							// Default, when address config is left out or empty, is "localhost"
	port: 8080,
	basePath: "/",	// The URL path where MagicMirror² is hosted. If you are using a Reverse proxy
									// you must set the sub path here. basePath must end with a /
	ipWhitelist: ["127.0.0.1", "::ffff:127.0.0.1", "::1"],	// Set [] to allow all IP addresses
									// or add a specific IPv4 of 192.168.1.5 :
									// ["127.0.0.1", "::ffff:127.0.0.1", "::1", "::ffff:192.168.1.5"],
									// or IPv4 range of 192.168.3.0 --> 192.168.3.15 use CIDR format :
									// ["127.0.0.1", "::ffff:127.0.0.1", "::1", "::ffff:192.168.3.0/28"],

	useHttps: false,			// Support HTTPS or not, default "false" will use HTTP
	httpsPrivateKey: "",	// HTTPS private key path, only require when useHttps is true
	httpsCertificate: "",	// HTTPS Certificate path, only require when useHttps is true

	language: "vi",
	locale: "vi-VN",   // this variable is provided as a consistent location
			   // it is currently only used by 3rd party modules. no MagicMirror code uses this value
			   // as we have no usage, we  have no constraints on what this field holds
			   // see https://en.wikipedia.org/wiki/Locale_(computer_software) for the possibilities

	logLevel: ["INFO", "LOG", "WARN", "ERROR", "DEBUG"], // Add "DEBUG" for even more logging
	timeFormat: 24,
	units: "metric",

	modules: [
		{
			module: "alert",
			classes: "known",
		},
		{
			module: "updatenotification",
			position: "top_bar",
			classes: "known"
		},
		{
			module: "clock",
			position: "top_left",
			classes: "everyone",
			config: {
				timeFormat: "HH:mm",
				displayType: "analog",
				dateFormat: "dddd, D MMMM YYYY",
				locale: "vi-VN",
				face: "modules/default/clock/faces/face-003.svg",  // CHƯA CHỈNH ĐƯỢC mặt đồng hồ
				displaySeconds: false,
				showPeriodUpper: false,
				clockBold: true,
				clockColor: "#FFFFFF",
				clockSize: 120
			},
		},
		{
			module: "calendar",
			header: "Lịch nghỉ lễ Việt Nam",
			position: "top_left",
			config: {
				calendars: [
					{
						fetchInterval: 7 * 24 * 60 * 60 * 1000,
						symbol: "calendar-check",
						url: "https://ics.calendarlabs.com/77/104efb3b/Vietnam_Holidays.ics"
					}
				]
			},
		},
		{
			module: "compliments",
			position: "lower_third",
			config: {
                compliments: {
                    anytime: [
                        "Xin chào người đẹp!",
                        "Hôm nay bạn trông thật tuyệt vời!",
                        "Nhớ làm xong deadline nha người đẹp!"
                    ]
                }
            },
			classes: "default",
		},
		{
			module: "weather",
			position: "top_right",
			header: "Dự báo thời tiết",
			config: {
				weatherProvider: "openmeteo",
				type: "forecast",
				lat: 10.7769,
                lon: 106.7009,
                units: "metric"
			},
		},
		{
			module: "newsfeed",
			position: "bottom_bar",
			config: {
				feeds: [
					{
						title: "Báo Thanh Niên",
						url: "https://thanhnien.vn/rss/home.rss"
					}
				],
				showSourceTitle: true,
				showPublishDate: true,
				broadcastNewsFeeds: true,
				broadcastNewsUpdates: true
			},
		},
		
		{
            module: "MMM-Keyboard",
            position: "fullscreen_above",
            config: {
                startWithNumbers: false,
                startUppercase: false,
                debug: false
            }
        },
        {
            module: "MMM-FSS-LivePreview",
            position: "middle_center",
            config: { previewFps: 10, timeoutAfterStable: 3000 }
        },
        {
            module: "MMM-FSS-Monitor",
            position: "top_center",
            config: {
                distanceThreshold: 0.6,
                showDebugInfo: false
            }
        },
        {
            module: "MMM-FSS-Env",
            position: "top_right",
            config: {
                updateInterval: 2000,
                roundTemperature: false,
                roundHumidity: false,
                displayUnits: true
            }
        },
        {
            module: "MMM-FSS-Recommend",
            position: "bottom_center"
        },
        {
            module: "MMM-FSS-Inventory",
            position: "bottom_right",
            config: {
                notificationDuration: 3000,
                frtAppEnabled: true,
                showPlaceholder: false
            }
        },
        {
            module: "MMM-FSS-Notification",
            position: "middle_center"
        },
	]
};

/*************** DO NOT EDIT THE LINE BELOW ***************/
if (typeof module !== "undefined") { module.exports = config; }
