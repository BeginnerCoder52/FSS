#include <sdbus-c++/sdbus-c++.h>
#include <iostream>
#include <string>
#include <vector>
#include <memory>
#include <thread>

using namespace std;

// D-Bus definitions
const std::string DBDAEMON_SERVICE = "vn.edu.uit.FSS.DBDaemon";
const std::string DBDAEMON_PATH = "/vn/edu/uit/FSS/DBDaemon";
const std::string DBDAEMON_INTERFACE = "vn.edu.uit.FSS.DBDaemon";

const std::string FRTAPP_SERVICE = "vn.edu.uit.FSS.FRTApp";
const std::string FRTAPP_PATH = "/vn/edu/uit/FSS/FRTApp";
const std::string FRTAPP_INTERFACE = "vn.edu.uit.FSS.FRTApp";

// Feature structure
struct Feature {
    std::string name;
    std::string food_id;
    int32_t quantity;
    std::string image_path;
    bool is_dbdaemon; // true = DBDaemon (UIUpdateRequired), false = FRTApp (FRTDetectionResult)
};

void printMenu(const std::vector<Feature>& features) {
    cout << "\n============================================\n";
    cout << "     FSS Mock CLI - D-Bus Signal Emitter    \n";
    cout << "============================================\n";
    for (size_t i = 0; i < features.size(); ++i) {
        cout << i + 1 << ". " << features[i].name << "\n";
    }
    cout << "0. Thoat (Exit)\n";
    cout << "============================================\n";
    cout << "Chon chuc nang (0-" << features.size() << "): ";
}

int main() {
    try {
        // Create a nameless system bus connection
        auto connection = sdbus::createSystemBusConnection();
        
        // Request names to simulate the daemons
        try {
            connection->requestName(DBDAEMON_SERVICE);
            cout << "[INFO] Successfully requested name: " << DBDAEMON_SERVICE << endl;
        } catch (const sdbus::Error& e) {
            cerr << "[WARNING] Could not request " << DBDAEMON_SERVICE << ": " << e.getMessage() << endl;
            cerr << "Make sure the real DBDaemon is not running." << endl;
        }

        try {
            connection->requestName(FRTAPP_SERVICE);
            cout << "[INFO] Successfully requested name: " << FRTAPP_SERVICE << endl;
        } catch (const sdbus::Error& e) {
            cerr << "[WARNING] Could not request " << FRTAPP_SERVICE << ": " << e.getMessage() << endl;
            cerr << "Make sure the real FRTApp is not running." << endl;
        }

        // Create objects to emit signals from
        auto db_obj = sdbus::createObject(*connection, DBDAEMON_PATH);
        auto frt_obj = sdbus::createObject(*connection, FRTAPP_PATH);

        // Enter processing loop in a separate thread so we can respond to D-Bus messages if needed
        connection->enterEventLoopAsync();

        // Define features table
        std::vector<Feature> features = {
            {"[DBDaemon] Them 3 Apple", "Apple", 3, "/opt/fss/images/apple.jpg", true},
            {"[DBDaemon] Xoa Apple (qty=0)", "Apple", 0, "", true},
            {"[DBDaemon] Them 5 Orange", "Orange", 5, "/opt/fss/images/orange.jpg", true},
            {"[DBDaemon] Xoa Orange (qty=0)", "Orange", 0, "", true},
            {"[FRTApp] Phat hien 2 Banana", "Banana", 2, "/opt/fss/images/banana.jpg", false},
            {"[FRTApp] Mat Banana (qty=0)", "Banana", 0, "", false}
        };

        while (true) {
            printMenu(features);
            int choice;
            if (!(cin >> choice)) {
                cin.clear();
                cin.ignore(10000, '\n');
                continue;
            }

            if (choice == 0) {
                cout << "Exiting...\n";
                break;
            }

            if (choice > 0 && choice <= static_cast<int>(features.size())) {
                const auto& feature = features[choice - 1];
                
                try {
                    if (feature.is_dbdaemon) {
                        cout << "[EMIT] DBDaemon UIUpdateRequired: " << feature.food_id << ", qty=" << feature.quantity << endl;
                        auto signal = db_obj->createSignal(DBDAEMON_INTERFACE, "UIUpdateRequired");
                        signal << feature.food_id << feature.quantity << feature.image_path;
                        db_obj->emitSignal(signal);
                    } else {
                        cout << "[EMIT] FRTApp FRTDetectionResult: " << feature.food_id << ", qty=" << feature.quantity << endl;
                        auto signal = frt_obj->createSignal(FRTAPP_INTERFACE, "FRTDetectionResult");
                        signal << feature.food_id << feature.quantity << feature.image_path;
                        frt_obj->emitSignal(signal);
                    }
                    cout << "[SUCCESS] Signal emitted." << endl;
                } catch (const sdbus::Error& e) {
                    cerr << "[ERROR] Failed to emit signal: " << e.getMessage() << endl;
                }
            } else {
                cout << "Invalid choice!\n";
            }
        }

        connection->leaveEventLoop();
        
    } catch (const sdbus::Error& e) {
        cerr << "[FATAL] D-Bus error: " << e.getMessage() << endl;
        return 1;
    }

    return 0;
}
