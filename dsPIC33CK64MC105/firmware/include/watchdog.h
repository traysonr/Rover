/**
 * @file watchdog.h
 * @brief Command Watchdog Timer
 * @version 1.0
 * @date 2025-12-29
 */

#ifndef WATCHDOG_H
#define WATCHDOG_H

#include <stdint.h>
#include <stdbool.h>
#include "config.h"

// ============================================================================
// WATCHDOG STRUCTURE
// ============================================================================

typedef struct {
    uint32_t last_cmd_time_ms;      // Timestamp of last valid command
    uint16_t age_ms;                // Age since last command
    bool timeout_active;            // Watchdog timeout flag
} CommandWatchdog_t;

// ============================================================================
// FUNCTION PROTOTYPES
// ============================================================================

/**
 * @brief Initialize watchdog
 * @param watchdog Pointer to watchdog structure
 */
void watchdog_init(CommandWatchdog_t *watchdog);

/**
 * @brief Feed watchdog (call when valid command received)
 * @param watchdog Pointer to watchdog structure
 * @param current_time_ms Current system time in milliseconds
 */
void watchdog_feed(CommandWatchdog_t *watchdog, uint32_t current_time_ms);

/**
 * @brief Update watchdog state (call at 1 kHz)
 * @param watchdog Pointer to watchdog structure
 * @param current_time_ms Current system time in milliseconds
 * @return true if timeout occurred
 */
bool watchdog_update(CommandWatchdog_t *watchdog, uint32_t current_time_ms);

/**
 * @brief Get age since last command
 * @param watchdog Pointer to watchdog structure
 * @return Age in milliseconds
 */
uint16_t watchdog_get_age(const CommandWatchdog_t *watchdog);

#endif // WATCHDOG_H

