/**
 * @file protocol.c
 * @brief UART Protocol Implementation
 * @version 1.0
 * @date 2025-12-29
 */

#include "protocol.h"
#include <string.h>
#include <stdlib.h>

// ============================================================================
// CRC-16/CCITT-FALSE IMPLEMENTATION
// ============================================================================

uint16_t crc16_ccitt(const uint8_t *data, uint16_t length) {
    uint16_t crc = 0xFFFF;
    
    for (uint16_t i = 0; i < length; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc = crc << 1;
            }
        }
    }
    
    return crc;
}

// ============================================================================
// PARSER IMPLEMENTATION
// ============================================================================

void protocol_parser_init(ProtocolParser_t *parser) {
    parser->state = PARSE_STATE_SCANNING_SOF;
    parser->sof_buf[0] = 0;
    parser->sof_buf[1] = 0;
    parser->header_idx = 0;
    parser->payload_idx = 0;
    parser->crc_idx = 0;
    parser->frames_received = 0;
    parser->crc_errors = 0;
    parser->version_errors = 0;
    parser->length_errors = 0;
}

bool protocol_parser_feed_byte(ProtocolParser_t *parser, uint8_t byte) {
    switch (parser->state) {
        case PARSE_STATE_SCANNING_SOF:
            // Shift SOF buffer
            parser->sof_buf[0] = parser->sof_buf[1];
            parser->sof_buf[1] = byte;
            
            // Check for SOF pattern
            if (parser->sof_buf[0] == SOF_BYTE_0 && parser->sof_buf[1] == SOF_BYTE_1) {
                parser->state = PARSE_STATE_READING_HEADER;
                parser->header_idx = 0;
            }
            break;
            
        case PARSE_STATE_READING_HEADER:
            parser->header_buf[parser->header_idx++] = byte;
            
            if (parser->header_idx >= 4) {
                // Parse header
                parser->frame.version = parser->header_buf[0];
                parser->frame.msg_type = parser->header_buf[1];
                parser->frame.seq = parser->header_buf[2];
                parser->frame.len = parser->header_buf[3];
                
                // Validate version
                if (parser->frame.version != PROTOCOL_VERSION) {
                    parser->version_errors++;
                    parser->state = PARSE_STATE_SCANNING_SOF;
                    break;
                }
                
                // Validate length
                if (parser->frame.len > FRAME_MAX_PAYLOAD) {
                    parser->length_errors++;
                    parser->state = PARSE_STATE_SCANNING_SOF;
                    break;
                }
                
                // Move to payload reading (or CRC if len==0)
                parser->payload_idx = 0;
                if (parser->frame.len > 0) {
                    parser->state = PARSE_STATE_READING_PAYLOAD;
                } else {
                    parser->state = PARSE_STATE_READING_CRC;
                    parser->crc_idx = 0;
                }
            }
            break;
            
        case PARSE_STATE_READING_PAYLOAD:
            parser->frame.payload[parser->payload_idx++] = byte;
            
            if (parser->payload_idx >= parser->frame.len) {
                parser->state = PARSE_STATE_READING_CRC;
                parser->crc_idx = 0;
            }
            break;
            
        case PARSE_STATE_READING_CRC:
            parser->crc_buf[parser->crc_idx++] = byte;
            
            if (parser->crc_idx >= 2) {
                // Extract CRC (little-endian)
                parser->frame.crc = parser->crc_buf[0] | ((uint16_t)parser->crc_buf[1] << 8);
                
                // Compute CRC over header + payload
                uint8_t crc_data[4 + FRAME_MAX_PAYLOAD];
                memcpy(crc_data, parser->header_buf, 4);
                if (parser->frame.len > 0) {
                    memcpy(crc_data + 4, parser->frame.payload, parser->frame.len);
                }
                uint16_t computed_crc = crc16_ccitt(crc_data, 4 + parser->frame.len);
                
                // Validate CRC
                if (computed_crc == parser->frame.crc) {
                    parser->frames_received++;
                    parser->state = PARSE_STATE_SCANNING_SOF;
                    return true;  // Valid frame received
                } else {
                    parser->crc_errors++;
                    parser->state = PARSE_STATE_SCANNING_SOF;
                }
            }
            break;
    }
    
    return false;  // No complete frame yet
}

// ============================================================================
// ENCODER IMPLEMENTATION
// ============================================================================

void protocol_encode_frame(uint8_t *buffer, uint16_t *length,
                          uint8_t msg_type, uint8_t seq,
                          const uint8_t *payload, uint8_t payload_len) {
    uint16_t idx = 0;
    
    // SOF
    buffer[idx++] = SOF_BYTE_0;
    buffer[idx++] = SOF_BYTE_1;
    
    // Header
    buffer[idx++] = PROTOCOL_VERSION;
    buffer[idx++] = msg_type;
    buffer[idx++] = seq;
    buffer[idx++] = payload_len;
    
    // Payload
    if (payload_len > 0) {
        memcpy(&buffer[idx], payload, payload_len);
        idx += payload_len;
    }
    
    // Compute CRC over header + payload
    uint16_t crc = crc16_ccitt(&buffer[2], 4 + payload_len);
    
    // Append CRC (little-endian)
    buffer[idx++] = (uint8_t)(crc & 0xFF);
    buffer[idx++] = (uint8_t)(crc >> 8);
    
    *length = idx;
}

// ============================================================================
// DECODER IMPLEMENTATIONS
// ============================================================================

bool protocol_decode_drive_cmd(const Frame_t *frame, DriveCmdPayload_t *cmd) {
    if (frame->msg_type != MSG_TYPE_DRIVE_CMD) {
        return false;
    }
    
    if (frame->len != sizeof(DriveCmdPayload_t)) {
        return false;
    }
    
    // Extract payload (assumes little-endian MCU)
    memcpy(cmd, frame->payload, sizeof(DriveCmdPayload_t));
    
    return true;
}

// ============================================================================
// ASCII PROTOCOL IMPLEMENTATION
// ============================================================================

bool ascii_parse_line(const char *line, DriveCmdPayload_t *cmd, bool *is_stop) {
    *is_stop = false;
    
    // Stop command: "S"
    if (line[0] == 'S' && (line[1] == '\n' || line[1] == '\0')) {
        *is_stop = true;
        return true;
    }
    
    // Drive command: "D <left> <right>"
    if (line[0] == 'D' && line[1] == ' ') {
        float left_f, right_f;
        int parsed = sscanf(&line[2], "%f %f", &left_f, &right_f);
        
        if (parsed == 2) {
            // Clamp values
            if (left_f < -1.0f) left_f = -1.0f;
            if (left_f > 1.0f) left_f = 1.0f;
            if (right_f < -1.0f) right_f = -1.0f;
            if (right_f > 1.0f) right_f = 1.0f;
            
            // Convert to Q15
            cmd->left_q15 = (int16_t)(left_f * 32767.0f);
            cmd->right_q15 = (int16_t)(right_f * 32767.0f);
            cmd->flags = DRIVE_FLAG_ENABLE_REQUEST;  // Auto-enable in ASCII mode
            
            return true;
        }
    }
    
    // Enable command: "E"
    if (line[0] == 'E' && (line[1] == '\n' || line[1] == '\0')) {
        cmd->left_q15 = 0;
        cmd->right_q15 = 0;
        cmd->flags = DRIVE_FLAG_ENABLE_REQUEST;
        return true;
    }
    
    // Disable command: "X"
    if (line[0] == 'X' && (line[1] == '\n' || line[1] == '\0')) {
        cmd->left_q15 = 0;
        cmd->right_q15 = 0;
        cmd->flags = 0;
        *is_stop = true;
        return true;
    }
    
    return false;  // Invalid command
}

