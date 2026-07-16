# Makefile for MC-38 Door Sensor Driver Tests

CXX := g++
CXXFLAGS := -std=c++17 -Wall -Wextra -O2 `pkg-config --cflags libgpiod`
LDFLAGS := `pkg-config --libs libgpiod`

# Directories
INCLUDE_DIR := ../../include
MC38_INCLUDE_DIR := ../../../drivers/sensor/mc-38/include
SRC_DIR := ../../src
MC38_SRC_DIR := ../../../drivers/sensor/mc-38/src
TEST_DIR := .

# Source files
TEST_SOURCES := test_main.cpp DoorSensorTest.cpp
DRIVER_SOURCES := $(SRC_DIR)/DoorSensorDriver.cpp $(SRC_DIR)/GpioHandler.cpp $(MC38_SRC_DIR)/MC38.cpp
SOURCES := $(TEST_SOURCES) $(DRIVER_SOURCES)
OBJECTS := $(SOURCES:.cpp=.o)
TARGET := test_mc38_driver

# Default target
all: $(TARGET)

# Build executable
$(TARGET): $(OBJECTS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)
	@echo "✓ Build complete: $(TARGET)"

# Compile test source files
test_main.o: test_main.cpp
	$(CXX) $(CXXFLAGS) -I$(INCLUDE_DIR) -I$(MC38_INCLUDE_DIR) -c $< -o $@

DoorSensorTest.o: DoorSensorTest.cpp
	$(CXX) $(CXXFLAGS) -I$(INCLUDE_DIR) -I$(MC38_INCLUDE_DIR) -c $< -o $@

# Compile driver source files
$(SRC_DIR)/DoorSensorDriver.o: $(SRC_DIR)/DoorSensorDriver.cpp
	$(CXX) $(CXXFLAGS) -I$(INCLUDE_DIR) -I$(MC38_INCLUDE_DIR) -c $< -o $@

$(SRC_DIR)/GpioHandler.o: $(SRC_DIR)/GpioHandler.cpp
	$(CXX) $(CXXFLAGS) -I$(INCLUDE_DIR) -I$(MC38_INCLUDE_DIR) -c $< -o $@

$(MC38_SRC_DIR)/MC38.o: $(MC38_SRC_DIR)/MC38.cpp
	$(CXX) $(CXXFLAGS) -I$(MC38_INCLUDE_DIR) -c $< -o $@

# Run test with sudo
run: $(TARGET)
	sudo ./$(TARGET)

# Run with custom GPIO offset
run-gpio:
	@read -p "Enter GPIO offset (default 26): " gpio; \
	sudo ./$(TARGET) --gpio $${gpio:-26}

# Clean build artifacts
clean:
	rm -f $(OBJECTS) $(TARGET)
	rm -f $(SRC_DIR)/*.o $(MC38_SRC_DIR)/*.o
	@echo "✓ Cleaned up build artifacts"

# Help target
help:
	@echo "MC-38 Door Sensor Driver Test Makefile"
	@echo "======================================="
	@echo "make            - Build the test executable"
	@echo "make run        - Build and run tests (requires sudo)"
	@echo "make run-gpio   - Run with custom GPIO offset"
	@echo "make clean      - Remove build artifacts"
	@echo "make help       - Show this help message"

.PHONY: all run run-gpio clean help
