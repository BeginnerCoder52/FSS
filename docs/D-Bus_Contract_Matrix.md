# D‑Bus Contract Matrix

| Service | Interface | Signal | Payload | Consumed By |
|--------|-----------|--------|---------|-------------|
| `vn.edu.uit.FSS.Sensor` | `vn.edu.uit.FSS.Sensor` | `EnvironmentDataChanged` | `(double temperature, double humidity)` | `MMM-FSS-Env` |
| `vn.edu.uit.FSS.Sensor` | `vn.edu.uit.FSS.Sensor` | `DistanceDataChanged` | `(double distance_meters)` | `MMM-FSS-Monitor` |
| `vn.edu.uit.FSS.Sensor` | `vn.edu.uit.FSS.Sensor` | `DoorStateChanged` | `(string state)` | `MMM-FSS-Monitor` |
| `vn.edu.uit.FSS.Sensor` | `vn.edu.uit.FSS.Sensor` | `UserPresenceDetected` | `(bool present)` | `MMM-FSS-Monitor` |
| `vn.edu.uit.FSS.DBDaemon` | `vn.edu.uit.FSS.DBDaemon` | `DistanceAlert` | `(double distance, bool within_threshold)` | `MMM-FSS-Monitor` |
| `vn.edu.uit.FSS.DBDaemon` | `vn.edu.uit.FSS.DBDaemon` | `DoorStateUpdate` | `(string state, double timestamp)` | `MMM-FSS-Monitor` |
| `vn.edu.uit.FSS.DBDaemon` | `vn.edu.uit.FSS.DBDaemon` | `UIUpdateRequired` | `(string food_id, int quantity, string image_path, int delta)` | `MMM-FSS-Inventory` |
| `vn.edu.uit.FSS.RecommendDaemon` | `vn.edu.uit.FSS.RecommendDaemon` | `RecommendationUpdated` | `(string recipe, string batch_id)` | `MMM-FSS-Recommend` |

*All other signals are handled similarly; this matrix captures the newly added `UserPresenceDetected` signal.*
