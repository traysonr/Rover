/**
 * @file motor_control.h
 * @brief Motor Control and Ramping
 * @version 1.0
 * @date 2025-12-29
 */

#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H

#include <stdint.h>
#include <stdbool.h>
#include "config.h"

// ============================================================================
// MOTOR CONTROL STRUCTURES
// ============================================================================

typedef struct {
    int16_t target_pwm;     // Target PWM value (-10000 to +10000)
    int16_t current_pwm;    // Current PWM value (ramped)
    int16_t ramp_rate;      // Ramp rate (change per ms)
    bool enabled;           // Output enable flag
} MotorState_t;

typedef struct {
    MotorState_t motors[NUM_MOTORS];
    uint16_t fault_flags;
    SystemState_t system_state;
} MotorController_t;

// ============================================================================
// FUNCTION PROTOTYPES
// ============================================================================

/**
 * @brief Initialize motor control system
 */
void motor_init(void);

/**
 * @brief Initialize motor controller state
 * @param controller Pointer to motor controller
 */
void motor_controller_init(MotorController_t *controller);

/**
 * @brief Set motor target speed
 * @param controller Pointer to motor controller
 * @param motor Motor index (MOTOR_LEFT or MOTOR_RIGHT)
 * @param pwm_value Target PWM (-10000 to +10000)
 */
void motor_set_target(MotorController_t *controller, uint8_t motor, int16_t pwm_value);

/**
 * @brief Update motor ramping (call at 1 kHz)
 * @param controller Pointer to motor controller
 * @param is_estop Emergency stop flag (faster ramp)
 */
void motor_update_ramps(MotorController_t *controller, bool is_estop);

/**
 * @brief Apply PWM outputs to hardware
 * @param controller Pointer to motor controller
 */
void motor_apply_outputs(const MotorController_t *controller);

/**
 * @brief Disable all motor outputs (safe state)
 */
void motor_disable_all(MotorController_t *controller);

/**
 * @brief Enable motor outputs (if no faults)
 * @param controller Pointer to motor controller
 * @return true if enabled, false if faults present
 */
bool motor_enable(MotorController_t *controller);

/**
 * @brief Get current motor PWM
 * @param controller Pointer to motor controller
 * @param motor Motor index
 * @return Current PWM value
 */
int16_t motor_get_current_pwm(const MotorController_t *controller, uint8_t motor);

/**
 * @brief Convert Q15 speed to PWM value
 * @param q15_speed Speed in Q15 format (-32767 to +32767)
 * @return PWM value (-10000 to +10000)
 */
int16_t q15_to_pwm(int16_t q15_speed);

#endif // MOTOR_CONTROL_H

