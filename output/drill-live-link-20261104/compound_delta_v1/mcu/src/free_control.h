#ifndef FREE_CONTROL_H
#define FREE_CONTROL_H
#include "demo_core.h"
/* Display controller: yaw positive left, pitch positive up from saved park.
 * Human-selected pitch extent is -45..+68deg; yaw +/-90 calibration acceptance
 * is separate from raw-target arrival. Full power-cycle acceptance is pending. */
enum {FC_STARTUP=1,FC_HOMING,FC_READY,FC_FAULT,FC_LINK_WAIT,FC_CONFIG_LIMIT};
typedef struct {
    Demo link;
    uint32_t signature,state,boot_ms,last_bus_ms,last_poll_ms;
    uint32_t pending_ms,settle_ms,tx_reads,tx_moves,home_moves;
    uint16_t pending_origin,home_target;
    uint16_t home_baseline_first;
    uint32_t home_baseline_ms;
    uint8_t preflight,pending,pending_count,pending_address,pending_axis;
    uint8_t poll_axis,pose_axis,home_axis,home_wait,home_read;
    uint8_t home_baseline;
    uint8_t rx[16],used;
    uint32_t last_fault,first_fault,lost_reads,last_fault_ms,recoveries;
    uint8_t recovery_mask;
    uint32_t sync_frames;
    uint16_t configured_min[2],configured_max[2];
    uint8_t limit_phase,limit_writes,limit_result;
    uint8_t startup_pose_pending;
} FreeControl;
extern const volatile uint32_t free_saved_reference[4];
void fc_init(FreeControl *s,uint32_t now);
void fc_command(FreeControl *s,const uint8_t command[32],uint32_t now,uint8_t reply[32]);
size_t fc_poll(FreeControl *s,uint32_t now,uint8_t frame[18]);
void fc_byte(FreeControl *s,uint8_t byte,uint32_t now);
void fc_stop(FreeControl *s,uint32_t now);
int fc_limit_begin(FreeControl *s,uint32_t now);
int fc_target_raw(unsigned axis,int16_t centidegrees,uint16_t *raw);
int fc_startup_prepare(FreeControl *s,uint16_t move_ms,uint32_t now);
#endif
