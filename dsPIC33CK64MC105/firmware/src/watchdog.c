/**
 * @file watchdog.c
 * @brief Command Watchdog Implementation
 * @version 1.0
 * @date 2025-12-29
 */

#include "watchdog.h"

void watchdog_init(CommandWatchdog_t *watchdog) {
    watchdog->last_cmd_time_ms = 0;
    watchdog->age_ms = 0xFFFF;  // Max age initially
    watchdog->timeout_active = true;  // Start in timeout state
}

void watchdog_feed(CommandWatchdog_t *watchdog, uint32_t current_time_ms) {
    watchdog->last_cmd_time_ms = current_time_ms;
    watchdog->age_ms = 0;
    watchdog->timeout_active = false;
}

bool watchdog_update(CommandWatchdog_t *watchdog, uint32_t current_time_ms) {
    // Calculate age
    uint32_t age = current_time_ms - watchdog->last_cmd_time_ms;
    
    // Clamp to uint16 range
    if (age > 0xFFFF) {
        watchdog->age_ms = 0xFFFF;
    } else {
        watchdog->age_ms = (uint16_t)age;
    }
    
    // Check for timeout
    bool was_timeout = watchdog->timeout_active;
    watchdog->timeout_active = (watchdog->age_ms >= WATCHDOG_TIMEOUT_MS);
    
    // Return true on transition to timeout
    return (!was_timeout && watchdog->timeout_active);
}

uint16_t watchdog_get_age(const CommandWatchdog_t *watchdog) {
    return watchdog->age_ms;
}

