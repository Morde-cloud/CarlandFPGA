#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H
#include "free_control.h"
/* MTR5 preserves op1..5; op6 atomically applies one same-round compound delta.
 * speed_norm is a command proxy 0..1000, never measured motor RPM. */
enum {MC_DELTA=6,MC_KEEPALIVE=7,MC_STARTUP_PREPARE=8,MC_VALID=1,MC_PAUSE=2,MC_STOP=4};
typedef struct {
    uint32_t deadline_ms,commands,stops;
    uint16_t duty;
    uint8_t active;
    uint32_t run_id,command_seq;
    uint16_t speed_norm;
    uint8_t run_source,have_run,allow_new_run,delta_live;
    /* Accepted target only. Never part of the executed speed accumulator. */
    uint32_t prepared_run_id;
    uint16_t prepared_speed_permille;
    uint8_t prepared_source,prepared_valid;
} MotorRuntime;
void mc_init(MotorRuntime *m);
void mc_tick(MotorRuntime *m,FreeControl *g,uint32_t now);
void mc_stop(MotorRuntime *m,FreeControl *g,uint32_t now);
void mc_command(MotorRuntime *m,FreeControl *g,const uint8_t in[32],uint32_t now,uint8_t out[32]);
#endif
