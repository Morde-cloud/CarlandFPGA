#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H
#include "free_control.h"
/* Motor-only opcode5: duty0..300permille, lease100..500ms. Existing ARM1 and
 * shared source/sequence are required. It never queues a gimbal pose. */
typedef struct {
    uint32_t deadline_ms,commands,stops;
    uint16_t duty;
    uint8_t active;
} MotorRuntime;
void mc_init(MotorRuntime *m);
void mc_tick(MotorRuntime *m,FreeControl *g,uint32_t now);
void mc_command(MotorRuntime *m,FreeControl *g,const uint8_t in[32],uint32_t now,uint8_t out[32]);
#endif
