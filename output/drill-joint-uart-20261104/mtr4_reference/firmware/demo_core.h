#ifndef DEMO_CORE_H
#define DEMO_CORE_H
#include <stdint.h>
#include <stddef.h>
#define DEMO_FRAME_SIZE 32
#define DEMO_WATCHDOG_MS 500u
#define DEMO_REVERSE_MS 200u
#ifndef DEMO_YAW_BOUND_CDEG
#define DEMO_YAW_BOUND_CDEG 1500
#endif
#ifndef DEMO_PITCH_BOUND_CDEG
#define DEMO_PITCH_BOUND_CDEG 1500
#endif
#ifndef DEMO_GIMBAL_ONLY
#define DEMO_GIMBAL_ONLY 0
#endif
enum { DEMO_OK, DEMO_CRC, DEMO_FORMAT, DEMO_DISARMED, DEMO_RANGE,
       DEMO_REVERSE_WAIT, DEMO_SEQUENCE, DEMO_WATCHDOG, DEMO_SOURCE };
typedef struct {
    uint32_t last_seq, last_set_ms, stopped_ms, feedback_ms[2];
    uint16_t duty, raw[2], bus_errors;
    int16_t yaw, pitch;
    uint16_t move_ms;
    uint8_t armed, source, direction, have_seq, seen_feedback[2];
    uint8_t capabilities, bus_status, result, pose_pending;
    uint8_t pending_read_id;
    uint32_t pending_read_ms;
} Demo;
uint16_t demo_crc(const uint8_t *data, size_t size);
void demo_init(Demo *s, uint8_t capabilities);
void demo_tick(Demo *s, uint32_t now_ms);
void demo_command(Demo *s, const uint8_t in[32], uint32_t now_ms, uint8_t out[32]);
void demo_status(Demo *s, uint32_t seq, uint32_t now_ms, uint8_t out[32]);
size_t joho_move(uint8_t id, uint16_t position, uint16_t ms, uint8_t out[11]);
size_t joho_read(uint8_t id, uint8_t out[8]);
void demo_begin_read(Demo *s, uint8_t id, uint32_t now_ms);
int demo_bus_response(Demo *s, const uint8_t *frame, size_t n, uint32_t now_ms);
void demo_bus_error(Demo *s);
#endif
