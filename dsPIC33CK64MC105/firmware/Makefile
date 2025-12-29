# Makefile for dsPIC33CK64MC105 Rover Firmware
# Requires Microchip XC16 compiler

# Compiler and tools
CC = xc16-gcc
LD = xc16-gcc
OBJCOPY = xc16-bin2hex

# Device selection
DEVICE = 33CK64MC105
DEVICE_HEADER = p$(DEVICE).h

# Directories
SRC_DIR = src
INC_DIR = include
BUILD_DIR = build
BIN_DIR = bin

# Source files
SOURCES = $(wildcard $(SRC_DIR)/*.c)
OBJECTS = $(patsubst $(SRC_DIR)/%.c,$(BUILD_DIR)/%.o,$(SOURCES))

# Output files
TARGET = rover_firmware
ELF = $(BIN_DIR)/$(TARGET).elf
HEX = $(BIN_DIR)/$(TARGET).hex

# Compiler flags
CFLAGS = -mcpu=$(DEVICE) \
         -Wall -Wextra \
         -O2 \
         -omf=elf \
         -I$(INC_DIR) \
         -ffunction-sections -fdata-sections \
         -g

# Linker flags
LDFLAGS = -mcpu=$(DEVICE) \
          -omf=elf \
          -Wl,--gc-sections \
          -Wl,--heap=512 \
          -Wl,--stack=512

# Default target
all: directories $(HEX)

# Create directories
directories:
	@mkdir -p $(BUILD_DIR)
	@mkdir -p $(BIN_DIR)

# Compile source files
$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c
	$(CC) $(CFLAGS) -c $< -o $@

# Link
$(ELF): $(OBJECTS)
	$(LD) $(LDFLAGS) $(OBJECTS) -o $@

# Convert to hex
$(HEX): $(ELF)
	$(OBJCOPY) $<

# Clean
clean:
	rm -rf $(BUILD_DIR) $(BIN_DIR)

# Rebuild
rebuild: clean all

# Program device (requires PICkit or ICD)
program: $(HEX)
	@echo "Programming device..."
	@echo "TODO: Add programming command (e.g., pk2cmd or mdb.sh)"

# Phony targets
.PHONY: all clean rebuild program directories

# Dependencies (simplified - use makedepend for production)
$(BUILD_DIR)/main.o: $(INC_DIR)/config.h $(INC_DIR)/protocol.h $(INC_DIR)/motor_control.h $(INC_DIR)/watchdog.h $(INC_DIR)/telemetry.h
$(BUILD_DIR)/protocol.o: $(INC_DIR)/protocol.h
$(BUILD_DIR)/motor_control.o: $(INC_DIR)/motor_control.h $(INC_DIR)/config.h
$(BUILD_DIR)/watchdog.o: $(INC_DIR)/watchdog.h $(INC_DIR)/config.h
$(BUILD_DIR)/telemetry.o: $(INC_DIR)/telemetry.h $(INC_DIR)/protocol.h $(INC_DIR)/config.h

