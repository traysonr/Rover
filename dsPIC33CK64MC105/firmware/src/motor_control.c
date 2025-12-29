/**
 * @file motor_control.c
 * @brief Motor Control Implementation
 * @version 1.0
 * @date 2025-12-29
 */

#include "motor_control.h"
#include <stdlib.h>

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

static inline int16_t clamp_int16(int32_t value, int16_t min, int16_t max) {
    if (value < min) return min;
    if (value > max) return max;
    return (int16_t)value;
}

static inline int16_t sign(int16_t value) {
    if (value > 0) return 1;
    if (value < 0) return -1;
    return 0;
}

// ============================================================================
// HARDWARE ABSTRACTION (Placeholder - adapt to your hardware)
// ============================================================================

// These functions should be implemented based on your actual hardware setup
// For now, they're placeholders

static void set_pwm_duty(uint8_t motor, uint16_t duty_percent_x100) {
    // TODO: Implement PWM duty cycle setting
    // duty_percent_x100: 0 = 0%, 10000 = 100%
    // Example for motor driver:
    // if (motor == MOTOR_LEFT) {
    //     PDC1 = (duty_percent_x100 * PTPER) / 10000;
    // }
}

static void set_motor_direction(uint8_t motor, int8_t direction) {
    // TODO: Implement direction pin control
    // direction: +1 = forward, -1 = reverse, 0 = brake/coast
    
    // Example for L298N:
    // if (motor == MOTOR_LEFT) {
    //     if (direction > 0) {
    //         PIN_LEFT_DIR1 = 1;
    //         PIN_LEFT_DIR2 = 0;
    //     } else if (direction < 0) {
    //         PIN_LEFT_DIR1 = 0;
    //         PIN_LEFT_DIR2 = 1;
    //     } else {
    //         PIN_LEFT_DIR1 = 0;  // Coast
    //         PIN_LEFT_DIR2 = 0;
    //     }
    // }
}

// ============================================================================
// INITIALIZATION
// ============================================================================

void motor_init(void) {
    // TODO: Initialize PWM hardware
    // - Configure timers
    // - Set PWM frequency
    // - Initialize GPIO pins for direction control
    
    // Example pseudocode:
    // PTCONbits.PTEN = 0;  // Disable PWM
    // PTPER = (FCY / PWM_FREQUENCY_HZ) - 1;
    // Configure PWM channels...
    // PTCONbits.PTEN = 1;  // Enable PWM
    
    // Set all outputs to safe state
    set_pwm_duty(MOTOR_LEFT, 0);
    set_pwm_duty(MOTOR_RIGHT, 0);
    set_motor_direction(MOTOR_LEFT, 0);
    set_motor_direction(MOTOR_RIGHT, 0);
}

void motor_controller_init(MotorController_t *controller) {
    for (uint8_t i = 0; i < NUM_MOTORS; i++) {
        controller->motors[i].target_pwm = 0;
        controller->motors[i].current_pwm = 0;
        controller->motors[i].ramp_rate = NORMAL_RAMP_RATE;
        controller->motors[i].enabled = false;
    }
    
    controller->fault_flags = FAULT_NONE;
    controller->system_state = STATE_BOOT;
}

// ============================================================================
// MOTOR CONTROL FUNCTIONS
// ============================================================================

void motor_set_target(MotorController_t *controller, uint8_t motor, int16_t pwm_value) {
    if (motor >= NUM_MOTORS) return;
    
    // Clamp to valid range
    pwm_value = clamp_int16(pwm_value, -PWM_RESOLUTION, PWM_RESOLUTION);
    
    controller->motors[motor].target_pwm = pwm_value;
}

void motor_update_ramps(MotorController_t *controller, bool is_estop) {
    // Set ramp rate based on E-stop condition
    int16_t ramp_rate = is_estop ? ESTOP_RAMP_RATE : NORMAL_RAMP_RATE;
    
    for (uint8_t i = 0; i < NUM_MOTORS; i++) {
        MotorState_t *motor = &controller->motors[i];
        motor->ramp_rate = ramp_rate;
        
        // Calculate error
        int32_t error = (int32_t)motor->target_pwm - (int32_t)motor->current_pwm;
        
        if (error == 0) {
            // Already at target
            continue;
        }
        
        // Apply ramping
        if (abs(error) <= ramp_rate) {
            // Within one step of target
            motor->current_pwm = motor->target_pwm;
        } else {
            // Ramp towards target
            if (error > 0) {
                motor->current_pwm += ramp_rate;
            } else {
                motor->current_pwm -= ramp_rate;
            }
        }
        
        // Safety clamp
        motor->current_pwm = clamp_int16(motor->current_pwm, 
                                        -PWM_RESOLUTION, PWM_RESOLUTION);
    }
}

void motor_apply_outputs(const MotorController_t *controller) {
    for (uint8_t i = 0; i < NUM_MOTORS; i++) {
        const MotorState_t *motor = &controller->motors[i];
        
        if (!motor->enabled || controller->system_state != STATE_ENABLED) {
            // Outputs disabled - set to safe state
            set_pwm_duty(i, 0);
            set_motor_direction(i, 0);
        } else {
            // Outputs enabled - apply PWM
            int16_t pwm = motor->current_pwm;
            uint16_t duty = (uint16_t)abs(pwm);
            int8_t direction = sign(pwm);
            
            set_pwm_duty(i, duty);
            set_motor_direction(i, direction);
        }
    }
}

void motor_disable_all(MotorController_t *controller) {
    for (uint8_t i = 0; i < NUM_MOTORS; i++) {
        controller->motors[i].enabled = false;
        controller->motors[i].target_pwm = 0;
    }
    
    controller->system_state = STATE_FAULTED;
}

bool motor_enable(MotorController_t *controller) {
    // Check for latched faults
    uint16_t latched_faults = FAULT_DRIVER_FAULT | FAULT_OVERVOLTAGE | 
                             FAULT_UNDERVOLTAGE | FAULT_OVERCURRENT;
    
    if (controller->fault_flags & latched_faults) {
        return false;  // Cannot enable with latched faults
    }
    
    // Enable motors
    for (uint8_t i = 0; i < NUM_MOTORS; i++) {
        controller->motors[i].enabled = true;
    }
    
    controller->system_state = STATE_ENABLED;
    return true;
}

int16_t motor_get_current_pwm(const MotorController_t *controller, uint8_t motor) {
    if (motor >= NUM_MOTORS) return 0;
    return controller->motors[motor].current_pwm;
}

// ============================================================================
// CONVERSION FUNCTIONS
// ============================================================================

int16_t q15_to_pwm(int16_t q15_speed) {
    // Convert Q15 (-32767 to +32767) to PWM (-10000 to +10000)
    // PWM = (Q15 * 10000) / 32767
    int32_t pwm = ((int32_t)q15_speed * PWM_RESOLUTION) / 32767;
    return clamp_int16(pwm, -PWM_RESOLUTION, PWM_RESOLUTION);
}

