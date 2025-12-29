/**
 * @file telemetry.h
 * @brief Telemetry Transmission
 * @version 1.0
 * @date 2025-12-29
 */

#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <stdint.h>
#include "config.h"
#include "protocol.h"

// ============================================================================
// TELEMETRY STRUCTURE
// ============================================================================

typedef struct {
    uint32_t last_tx_time_ms;       // Last transmission time
    uint8_t seq_num;                // Sequence number for frames
} TelemetryState_t;

// ============================================================================
// FUNCTION PROTOTYPES
// ============================================================================

/**
 * @brief Initialize telemetry state
 * @param telem Pointer to telemetry state
 */
void telemetry_init(TelemetryState_t *telem);

/**
 * @brief Check if telemetry should be sent
 * @param telem Pointer to telemetry state
 * @param current_time_ms Current system time
 * @return true if time to send telemetry
 */
bool telemetry_should_send(const TelemetryState_t *telem, uint32_t current_time_ms);

/**
 * @brief Send telemetry frame
 * @param telem Pointer to telemetry state
 * @param payload Telemetry payload to send
 * @param current_time_ms Current system time
 */
void telemetry_send(TelemetryState_t *telem, const TelemetryPayload_t *payload, 
                   uint32_t current_time_ms);

#endif // TELEMETRY_H

