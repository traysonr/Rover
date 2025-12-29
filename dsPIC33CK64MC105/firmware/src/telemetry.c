/**
 * @file telemetry.c
 * @brief Telemetry Transmission Implementation
 * @version 1.0
 * @date 2025-12-29
 */

#include "telemetry.h"
#include <string.h>

// External UART transmit function (to be implemented in uart.c)
extern void uart_transmit_bytes(const uint8_t *data, uint16_t length);

void telemetry_init(TelemetryState_t *telem) {
    telem->last_tx_time_ms = 0;
    telem->seq_num = 0;
}

bool telemetry_should_send(const TelemetryState_t *telem, uint32_t current_time_ms) {
    uint32_t elapsed = current_time_ms - telem->last_tx_time_ms;
    return (elapsed >= TELEMETRY_PERIOD_MS);
}

void telemetry_send(TelemetryState_t *telem, const TelemetryPayload_t *payload,
                   uint32_t current_time_ms) {
    uint8_t frame_buffer[64];  // Large enough for telemetry frame
    uint16_t frame_length;
    
    // Encode frame
    protocol_encode_frame(frame_buffer, &frame_length,
                         MSG_TYPE_TELEMETRY, telem->seq_num,
                         (const uint8_t *)payload, sizeof(TelemetryPayload_t));
    
    // Transmit
    uart_transmit_bytes(frame_buffer, frame_length);
    
    // Update state
    telem->seq_num++;
    telem->last_tx_time_ms = current_time_ms;
}

