/**
 * @file protocol.h
 * @brief UART Protocol Definitions
 * @version 1.0
 * @date 2025-12-29
 */

#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>
#include <stdbool.h>

// ============================================================================
// BINARY PROTOCOL (Version 1)
// ============================================================================

// Start of frame marker
#define SOF_BYTE_0          0xAA
#define SOF_BYTE_1          0x55

// Protocol version
#define PROTOCOL_VERSION    0x01

// Message types
typedef enum {
    MSG_TYPE_DRIVE_CMD      = 0x01,     // Pi → dsPIC: Drive command
    MSG_TYPE_STOP_CMD       = 0x02,     // Pi → dsPIC: Stop
    MSG_TYPE_TELEMETRY      = 0x10,     // dsPIC → Pi: Status
    MSG_TYPE_ENCODER_DATA   = 0x11,     // dsPIC → Pi: Encoder data [Phase 2]
    MSG_TYPE_HEARTBEAT      = 0xFE,     // Bidirectional: Keepalive
    MSG_TYPE_ERROR_REPORT   = 0xFF,     // dsPIC → Pi: Error details
} MessageType_t;

// Frame structure
#define FRAME_SOF_SIZE      2
#define FRAME_HEADER_SIZE   4   // Version, MsgType, Seq, Len
#define FRAME_CRC_SIZE      2
#define FRAME_OVERHEAD      (FRAME_SOF_SIZE + FRAME_HEADER_SIZE + FRAME_CRC_SIZE)
#define FRAME_MAX_PAYLOAD   255

// Parser states
typedef enum {
    PARSE_STATE_SCANNING_SOF,
    PARSE_STATE_READING_HEADER,
    PARSE_STATE_READING_PAYLOAD,
    PARSE_STATE_READING_CRC,
} ParserState_t;

// Frame structure
typedef struct {
    uint8_t version;
    uint8_t msg_type;
    uint8_t seq;
    uint8_t len;
    uint8_t payload[FRAME_MAX_PAYLOAD];
    uint16_t crc;
} Frame_t;

// ============================================================================
// MESSAGE PAYLOADS
// ============================================================================

// DriveCmd payload (6 bytes)
typedef struct __attribute__((packed)) {
    int16_t left_q15;       // Left motor speed in Q15 format
    int16_t right_q15;      // Right motor speed in Q15 format
    uint16_t flags;         // Control flags
} DriveCmdPayload_t;

// Telemetry payload (10 bytes)
typedef struct __attribute__((packed)) {
    int16_t left_pwm;       // Left motor PWM duty (-10000 to +10000)
    int16_t right_pwm;      // Right motor PWM duty
    uint16_t bus_mv;        // Bus voltage in millivolts
    uint16_t fault_flags;   // Active fault flags
    uint16_t age_ms;        // Milliseconds since last valid command
} TelemetryPayload_t;

// EncoderData payload (16 bytes) [Phase 2]
typedef struct __attribute__((packed)) {
    int32_t left_ticks;     // Cumulative encoder ticks (left)
    int32_t right_ticks;    // Cumulative encoder ticks (right)
    int16_t left_vel;       // Instantaneous velocity (ticks/sec)
    int16_t right_vel;      // Instantaneous velocity (ticks/sec)
    uint32_t timestamp;     // Millisecond timestamp
} EncoderDataPayload_t;

// ============================================================================
// PARSER CONTEXT
// ============================================================================

typedef struct {
    ParserState_t state;
    uint8_t sof_buf[2];     // Buffer for SOF detection
    uint8_t header_buf[4];  // Buffer for header
    uint8_t header_idx;
    Frame_t frame;
    uint16_t payload_idx;
    uint8_t crc_buf[2];
    uint8_t crc_idx;
    
    // Statistics
    uint32_t frames_received;
    uint32_t crc_errors;
    uint32_t version_errors;
    uint32_t length_errors;
} ProtocolParser_t;

// ============================================================================
// ASCII PROTOCOL (Version 0 - Fallback)
// ============================================================================

#define ASCII_MAX_LINE_LEN  128
#define ASCII_LINE_TERM     '\n'

// ============================================================================
// FUNCTION PROTOTYPES
// ============================================================================

// CRC calculation
uint16_t crc16_ccitt(const uint8_t *data, uint16_t length);

// Parser functions
void protocol_parser_init(ProtocolParser_t *parser);
bool protocol_parser_feed_byte(ProtocolParser_t *parser, uint8_t byte);

// Encoder functions
void protocol_encode_frame(uint8_t *buffer, uint16_t *length, 
                          uint8_t msg_type, uint8_t seq,
                          const uint8_t *payload, uint8_t payload_len);

// Decoder functions
bool protocol_decode_drive_cmd(const Frame_t *frame, DriveCmdPayload_t *cmd);

// ASCII protocol functions
bool ascii_parse_line(const char *line, DriveCmdPayload_t *cmd, bool *is_stop);

#endif // PROTOCOL_H

