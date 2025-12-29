/**
 * @file main.c
 * @brief Rover dsPIC Firmware - Main Control Loop
 * @version 1.0
 * @date 2025-12-29
 * 
 * Phase 1 Implementation:
 * - Binary/ASCII UART protocol
 * - Motor PWM control with ramping
 * - Command watchdog
 * - Telemetry transmission
 * - Fault management
 */

#include "config.h"
#include "protocol.h"
#include "motor_control.h"
#include "watchdog.h"
#include "telemetry.h"
#include <stdint.h>
#include <stdbool.h>

// ============================================================================
// GLOBAL STATE
// ============================================================================

// System time (milliseconds, updated by timer ISR)
volatile uint32_t g_system_time_ms = 0;

// Protocol and control state
static ProtocolParser_t g_parser;
static MotorController_t g_motor_controller;
static CommandWatchdog_t g_watchdog;
static TelemetryState_t g_telemetry;

// Voltage monitoring (placeholder - implement ADC reading)
static uint16_t g_bus_voltage_mv = VOLTAGE_NOMINAL_MV;

// ============================================================================
// HARDWARE INITIALIZATION (Placeholders)
// ============================================================================

/**
 * @brief Initialize system clock
 */
static void clock_init(void) {
    // TODO: Configure PLL for 100 MHz (FCY)
    // This is device-specific - refer to dsPIC33CK datasheet
}

/**
 * @brief Initialize 1 kHz timer for control loop
 */
static void timer_init(void) {
    // TODO: Configure Timer1 for 1 ms interrupt
    // Example pseudocode:
    // T1CONbits.TON = 0;       // Disable timer
    // T1CONbits.TCS = 0;       // Use internal clock
    // T1CONbits.TCKPS = 0b01;  // Prescaler 1:8
    // PR1 = (FCY / 8 / 1000) - 1;  // 1 ms period
    // IFS0bits.T1IF = 0;       // Clear interrupt flag
    // IEC0bits.T1IE = 1;       // Enable interrupt
    // T1CONbits.TON = 1;       // Enable timer
}

/**
 * @brief Initialize UART hardware
 */
static void uart_init(void) {
    // TODO: Configure UART1 for 115200 8N1
    // Example pseudocode:
    // U1MODEbits.UARTEN = 0;   // Disable UART
    // U1BRG = (FCY / (16 * UART_BAUDRATE)) - 1;
    // U1MODEbits.PDSEL = 0;    // 8-bit data, no parity
    // U1MODEbits.STSEL = 0;    // 1 stop bit
    // U1STAbits.UTXEN = 1;     // Enable transmit
    // IEC0bits.U1RXIE = 1;     // Enable RX interrupt
    // U1MODEbits.UARTEN = 1;   // Enable UART
}

/**
 * @brief Initialize ADC for voltage monitoring
 */
static void adc_init(void) {
    // TODO: Configure ADC for bus voltage measurement
}

/**
 * @brief Read bus voltage from ADC
 * @return Voltage in millivolts
 */
static uint16_t read_bus_voltage(void) {
    // TODO: Read ADC and convert to millivolts
    // Placeholder: return nominal voltage
    return VOLTAGE_NOMINAL_MV;
}

// ============================================================================
// UART FUNCTIONS
// ============================================================================

/**
 * @brief Transmit bytes over UART (blocking)
 */
void uart_transmit_bytes(const uint8_t *data, uint16_t length) {
    // TODO: Implement UART transmission
    // Example pseudocode:
    // for (uint16_t i = 0; i < length; i++) {
    //     while (U1STAbits.UTXBF);  // Wait for TX buffer space
    //     U1TXREG = data[i];
    // }
}

/**
 * @brief UART RX interrupt handler (called from ISR)
 */
static void uart_rx_handler(uint8_t byte) {
    // Feed byte to protocol parser
    bool frame_ready = protocol_parser_feed_byte(&g_parser, byte);
    
    if (frame_ready) {
        // Process received frame
        process_received_frame(&g_parser.frame);
    }
}

// ============================================================================
// MESSAGE PROCESSING
// ============================================================================

/**
 * @brief Process a received protocol frame
 */
static void process_received_frame(const Frame_t *frame) {
    switch (frame->msg_type) {
        case MSG_TYPE_DRIVE_CMD: {
            DriveCmdPayload_t cmd;
            if (protocol_decode_drive_cmd(frame, &cmd)) {
                // Feed watchdog
                watchdog_feed(&g_watchdog, g_system_time_ms);
                
                // Check for E-stop
                if (cmd.flags & DRIVE_FLAG_ESTOP) {
                    g_motor_controller.fault_flags |= FAULT_ESTOP_ACTIVE;
                    motor_set_target(&g_motor_controller, MOTOR_LEFT, 0);
                    motor_set_target(&g_motor_controller, MOTOR_RIGHT, 0);
                    motor_disable_all(&g_motor_controller);
                } else {
                    // Clear E-stop if not set
                    g_motor_controller.fault_flags &= ~FAULT_ESTOP_ACTIVE;
                    
                    // Handle enable request
                    if (cmd.flags & DRIVE_FLAG_ENABLE_REQUEST) {
                        if (g_motor_controller.system_state != STATE_ENABLED) {
                            motor_enable(&g_motor_controller);
                        }
                    }
                    
                    // Set motor targets
                    if (g_motor_controller.system_state == STATE_ENABLED) {
                        int16_t left_pwm = q15_to_pwm(cmd.left_q15);
                        int16_t right_pwm = q15_to_pwm(cmd.right_q15);
                        motor_set_target(&g_motor_controller, MOTOR_LEFT, left_pwm);
                        motor_set_target(&g_motor_controller, MOTOR_RIGHT, right_pwm);
                    }
                }
            }
            break;
        }
        
        case MSG_TYPE_STOP_CMD: {
            // Explicit stop
            g_motor_controller.fault_flags |= FAULT_ESTOP_ACTIVE;
            motor_set_target(&g_motor_controller, MOTOR_LEFT, 0);
            motor_set_target(&g_motor_controller, MOTOR_RIGHT, 0);
            motor_disable_all(&g_motor_controller);
            break;
        }
        
        default:
            // Unknown message type - ignore
            break;
    }
}

// ============================================================================
// FAULT CHECKING
// ============================================================================

/**
 * @brief Check for fault conditions and update flags
 */
static void check_faults(void) {
    uint16_t faults = g_motor_controller.fault_flags;
    
    // Check voltage
    g_bus_voltage_mv = read_bus_voltage();
    
    if (g_bus_voltage_mv < VOLTAGE_MIN_MV) {
        faults |= FAULT_UNDERVOLTAGE;
    } else {
        faults &= ~FAULT_UNDERVOLTAGE;  // Non-latched, clears when resolved
    }
    
    if (g_bus_voltage_mv > VOLTAGE_MAX_MV) {
        faults |= FAULT_OVERVOLTAGE;
    } else {
        faults &= ~FAULT_OVERVOLTAGE;
    }
    
    // Check watchdog
    if (watchdog_update(&g_watchdog, g_system_time_ms)) {
        // Watchdog timeout occurred
        faults |= FAULT_WATCHDOG_TIMEOUT;
        motor_set_target(&g_motor_controller, MOTOR_LEFT, 0);
        motor_set_target(&g_motor_controller, MOTOR_RIGHT, 0);
        motor_disable_all(&g_motor_controller);
    }
    
    if (g_watchdog.timeout_active) {
        faults |= FAULT_WATCHDOG_TIMEOUT;
    } else {
        faults &= ~FAULT_WATCHDOG_TIMEOUT;  // Clears when commands resume
    }
    
    // TODO: Check for other faults (motor driver fault pin, overcurrent, etc.)
    
    // Update fault flags
    g_motor_controller.fault_flags = faults;
    
    // If any latched faults, ensure motors disabled
    uint16_t latched = faults & (FAULT_DRIVER_FAULT | FAULT_OVERVOLTAGE | 
                                 FAULT_UNDERVOLTAGE | FAULT_OVERCURRENT);
    if (latched) {
        motor_disable_all(&g_motor_controller);
    }
}

// ============================================================================
// TELEMETRY TRANSMISSION
// ============================================================================

/**
 * @brief Send telemetry frame if due
 */
static void send_telemetry_if_due(void) {
    if (telemetry_should_send(&g_telemetry, g_system_time_ms)) {
        TelemetryPayload_t payload;
        
        payload.left_pwm = motor_get_current_pwm(&g_motor_controller, MOTOR_LEFT);
        payload.right_pwm = motor_get_current_pwm(&g_motor_controller, MOTOR_RIGHT);
        payload.bus_mv = g_bus_voltage_mv;
        payload.fault_flags = g_motor_controller.fault_flags;
        payload.age_ms = watchdog_get_age(&g_watchdog);
        
        telemetry_send(&g_telemetry, &payload, g_system_time_ms);
    }
}

// ============================================================================
// CONTROL LOOP (1 kHz)
// ============================================================================

/**
 * @brief Main control loop tick (called from timer ISR or main loop)
 */
static void control_loop_tick(void) {
    // 1. Check for faults
    check_faults();
    
    // 2. Update motor ramping
    bool is_estop = (g_motor_controller.fault_flags & FAULT_ESTOP_ACTIVE) != 0;
    motor_update_ramps(&g_motor_controller, is_estop);
    
    // 3. Apply motor outputs
    motor_apply_outputs(&g_motor_controller);
    
    // 4. Send telemetry if due
    send_telemetry_if_due();
}

// ============================================================================
// INTERRUPT SERVICE ROUTINES
// ============================================================================

/**
 * @brief Timer1 interrupt - 1 kHz control loop
 */
void __attribute__((interrupt, no_auto_psv)) _T1Interrupt(void) {
    // Clear interrupt flag
    // IFS0bits.T1IF = 0;
    
    // Increment system time
    g_system_time_ms++;
    
    // Run control loop
    control_loop_tick();
}

/**
 * @brief UART1 RX interrupt
 */
void __attribute__((interrupt, no_auto_psv)) _U1RXInterrupt(void) {
    // Clear interrupt flag
    // IFS0bits.U1RXIF = 0;
    
    // Read received byte
    // uint8_t byte = U1RXREG;
    
    // Process byte
    // uart_rx_handler(byte);
}

// ============================================================================
// MAIN
// ============================================================================

int main(void) {
    // Initialize hardware
    clock_init();
    timer_init();
    uart_init();
    adc_init();
    motor_init();
    
    // Initialize software modules
    protocol_parser_init(&g_parser);
    motor_controller_init(&g_motor_controller);
    watchdog_init(&g_watchdog);
    telemetry_init(&g_telemetry);
    
    // Start in BOOT state with outputs disabled
    g_motor_controller.system_state = STATE_BOOT;
    
    // Enable global interrupts
    // __builtin_enable_interrupts();
    
    // Main loop (most work done in ISRs)
    while (1) {
        // Optional: low-priority tasks here
        // - LED blinking based on state
        // - Diagnostics
        // - Low-frequency checks
        
        // For now, just idle (or enter low-power mode)
        // __builtin_nop();
    }
    
    return 0;
}

