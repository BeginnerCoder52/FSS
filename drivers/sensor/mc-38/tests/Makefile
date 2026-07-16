# Makefile for MC-38 Door Sensor Test
CXX      := g++
CXXFLAGS := -std=c++17 -Wall -Wextra -O2
LDFLAGS  := -lgpiodcxx -lgpiod   # C++ bindings first, then C core

# Directories
TEST_DIR := .

# Source files � standalone, no separate MC38.cpp needed
SOURCES  := test_mc38.cpp
OBJECTS  := $(SOURCES:.cpp=.o)
TARGET   := test_mc38

# Default target
all: $(TARGET)

# Build executable
$(TARGET): $(OBJECTS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)
	@echo "Build complete: $(TARGET)"

# Compile source files
%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Run test with sudo
run: $(TARGET)
	sudo ./$(TARGET)

# Clean build artifacts
clean:
	rm -f $(OBJECTS) $(TARGET)
	@echo "Cleaned up build artifacts"

# Help target
help:
	@echo "MC-38 Test Makefile"
	@echo "===================="
	@echo "make        - Build the test executable"
	@echo "make run    - Build and run (requires sudo)"
	@echo "make clean  - Remove build artifacts"
	@echo "make help   - Show this help message"

.PHONY: all run clean help