/**
 * @file config.h
 * @brief Rover dsPIC Firmware Configuration
 * @version 1.0
 * @date 2025-12-29
 */

#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>
#include <stdbool.h>

// ============================================================================
// FIRMWARE VERSION
// ============================================================================
#define FW_VERSION_MAJOR    1
#define FW_VERSION_MINOR    0
#define FW_VERSION_PATCH    0

// ============================================================================
// SYSTEM TIMING
// ============================================================================
#define FCY                 100000000UL     // 100 MHz instruction cycle
#define TIMER_FREQ_HZ       1000            // Main control loop: 1 kHz
#define TIMER_PERIOD_US     1000            // 1 ms period

// ============================================================================
// UART CONFIGURATION
// ============================================================================
#define UART_BAUDRATE       115200
#define UART_MODULE         1               // Use UART1
#define UART_RX_BUFFER_SIZE 256             // Must be power of 2
#define UART_TX_BUFFER_SIZE 256

// Protocol selection
#define PROTOCOL_VERSION_ASCII  0
#define PROTOCOL_VERSION_BINARY 1
#define DEFAULT_PROTOCOL        PROTOCOL_VERSION_BINARY

// ============================================================================
// PWM CONFIGURATION
// ============================================================================
#define PWM_FREQUENCY_HZ    20000           // 20 kHz for L298N
#define PWM_RESOLUTION      10000           // ±10000 = ±100.00%
#define PWM_DEADBAND        0               // No deadband for L298N

// Motor channels
#define MOTOR_LEFT          0
#define MOTOR_RIGHT         1
#define NUM_MOTORS          2

// ============================================================================
// PIN ASSIGNMENTS (Adjust for your hardware)
// ============================================================================
// Left motor
#define PIN_LEFT_PWM        _LATB0          // Example: RB0 for left PWM
#define PIN_LEFT_DIR1       _LATB1          // RB1 for left direction A
#define PIN_LEFT_DIR2       _LATB2          // RB2 for left direction B

// Right motor
#define PIN_RIGHT_PWM       _LATB3          // RB3 for right PWM
#define PIN_RIGHT_DIR1      _LATB4          // RB4 for right direction A
#define PIN_RIGHT_DIR2      _LATB5          // RB5 for right direction B

// Status LED
#define PIN_LED_STATUS      _LATB6          // RB6 for status LED
#define PIN_LED_FAULT       _LATB7          // RB7 for fault LED

// ============================================================================
// SAFETY PARAMETERS
// ============================================================================
#define WATCHDOG_TIMEOUT_MS     200         // Command timeout: 200 ms
#define ESTOP_RAMP_TIME_MS      50          // Fast ramp on E-stop: 50 ms
#define NORMAL_RAMP_TIME_MS     2000        // Normal ramp: 2 seconds (0→100%)

// Ramp rates (change per ms, scaled to PWM_RESOLUTION)
#define NORMAL_RAMP_RATE        (PWM_RESOLUTION / NORMAL_RAMP_TIME_MS)  // 5 per ms
#define ESTOP_RAMP_RATE         (PWM_RESOLUTION / ESTOP_RAMP_TIME_MS)   // 200 per ms

// Voltage thresholds (millivolts)
#define VOLTAGE_MIN_MV          9000        // 9V minimum (3S LiPo cutoff ~10.5V, margin)
#define VOLTAGE_MAX_MV          13000       // 13V maximum (3S LiPo max ~12.6V, margin)
#define VOLTAGE_NOMINAL_MV      11100       // 3S LiPo nominal

// ============================================================================
// TELEMETRY
// ============================================================================
#define TELEMETRY_RATE_HZ       20          // 20 Hz telemetry
#define TELEMETRY_PERIOD_MS     (1000 / TELEMETRY_RATE_HZ)

// ============================================================================
// FAULT FLAGS (matches protocol spec)
// ============================================================================
typedef enum {
    FAULT_NONE              = 0x0000,
    FAULT_WATCHDOG_TIMEOUT  = 0x0001,   // Bit 0
    FAULT_ESTOP_ACTIVE      = 0x0002,   // Bit 1
    FAULT_UNDERVOLTAGE      = 0x0004,   // Bit 2
    FAULT_OVERVOLTAGE       = 0x0008,   // Bit 3
    FAULT_DRIVER_FAULT      = 0x0010,   // Bit 4
    FAULT_OVERCURRENT       = 0x0020,   // Bit 5
    FAULT_THERMAL_WARNING   = 0x0040,   // Bit 6
} FaultFlags_t;

// ============================================================================
// SYSTEM STATES
// ============================================================================
typedef enum {
    STATE_BOOT,         // Power-on, outputs disabled, awaiting first enable
    STATE_ENABLED,      // Normal operation, executing commands
    STATE_FAULTED,      // Fault condition, outputs disabled
} SystemState_t;

// ============================================================================
// DRIVE FLAGS (matches protocol spec)
// ============================================================================
#define DRIVE_FLAG_ESTOP            0x0001  // Bit 0: Emergency stop
#define DRIVE_FLAG_ENABLE_REQUEST   0x0002  // Bit 1: Request enable

#endif // CONFIG_H

