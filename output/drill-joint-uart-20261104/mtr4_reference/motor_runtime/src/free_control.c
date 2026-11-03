#include "free_control.h"
#include <string.h>
#if !DEMO_GIMBAL_ONLY || DEMO_YAW_BOUND_CDEG != 9000 || DEMO_PITCH_BOUND_CDEG != 9000
#error Free control requires the explicit gimbal-only protocol profile
#endif
const volatile uint32_t free_saved_reference[4]={0x47524331u,1u,2088u,1961u};
static const uint16_t minimum[2]={610,400},maximum[2]={3550,3550};
static const uint16_t soft_minimum[2]={626,416},soft_maximum[2]={3534,3534};
static uint32_t gap(uint32_t a,uint32_t b) {return a>b?a-b:b-a;}
static uint16_t be16(const uint8_t *p) {return (uint16_t)(((uint16_t)p[0]<<8)|p[1]);}
static void disarm(FreeControl *s) {s->link.armed=0;s->link.duty=0;s->link.pose_pending=0;s->pose_axis=0;}
static void fault(FreeControl *s) {
    if(s->state==FC_CONFIG_LIMIT)s->limit_result=4;
    s->state=FC_FAULT;s->pending=0;s->home_wait=s->home_read=0;
    s->link.seen_feedback[0]=s->link.seen_feedback[1]=0;
    disarm(s);s->link.result=DEMO_DISARMED;demo_bus_error(&s->link);
}
static void read_timeout(FreeControl *s,uint32_t now) {
    s->last_fault=1;if(!s->first_fault)s->first_fault=1;
    s->last_fault_ms=now;s->lost_reads++;
    /* Continuing telemetry is not a replay of any actuator action. Startup or
     * unfinished home failures remain latched because motion may be partial. */
    if((s->state!=FC_READY && s->state!=FC_LINK_WAIT) || s->pending_address!=0x38) {fault(s);return;}
    s->state=FC_LINK_WAIT;s->pending=0;s->used=0;s->recovery_mask=0;
    s->link.seen_feedback[0]=s->link.seen_feedback[1]=0;
    disarm(s);s->link.result=DEMO_DISARMED;demo_bus_error(&s->link);
    s->last_poll_ms=now;
}
void fc_stop(FreeControl *s,uint32_t now) {
    (void)now;disarm(s);
    if(s->state==FC_STARTUP || s->state==FC_HOMING || s->state==FC_CONFIG_LIMIT) fault(s);
}
int fc_limit_begin(FreeControl *s,uint32_t now) {
    if(s->state!=FC_READY || s->pending || s->link.armed || s->limit_writes ||
       s->link.yaw || s->link.pitch || (uint32_t)(now-s->link.last_set_ms)<1500u ||
       !s->link.seen_feedback[0] || !s->link.seen_feedback[1] ||
       (uint32_t)(now-s->link.feedback_ms[0])>1000u || (uint32_t)(now-s->link.feedback_ms[1])>1000u ||
       gap(s->link.raw[0],2088)>32 || gap(s->link.raw[1],1961)>32) return 0;
    disarm(s);s->state=FC_CONFIG_LIMIT;s->used=0;s->limit_phase=0;s->limit_result=1;return 1;
}
int fc_target_raw(unsigned axis,int16_t angle,uint16_t *raw) {
    int32_t value;
    if(axis>1 || !raw || angle < -9000 || angle>9000 ||
       (axis==1 && (angle < -4500 || angle>6800))) return 0;
    /* Integer fixed-point models based on measured reference points, not an
     * assumed4096-to360deg servo specification. Latest large pitch reference:
     * Human large yaw references:3342=left83deg,829=right76deg. Right exact
     * extrapolation would exceed the configured minimum; gain16 intentionally
     * targets raw648 at90deg (roughly87deg physically), pending +/-5deg acceptance.
     * Selected pitch extent: old target3143=human78deg;1252=human-45deg.
     * Battery attachment reduces the permitted upper command to68deg (raw2991).
     * Preserve calibration gains and saved zero; never rescale68deg to the old78deg endpoint. */
    if(axis==0)value=2088+(angle>=0?(int32_t)angle*1254/8300:(int32_t)angle*16/100);
    else value=1961+(angle>=0?(int32_t)angle*1182/7800:(int32_t)angle*788/5000);
    if(value<soft_minimum[axis] || value>soft_maximum[axis] ||
       value<minimum[axis]+16 || value>maximum[axis]-16) return 0;
    *raw=(uint16_t)value;return 1;
}
void fc_init(FreeControl *s,uint32_t now) {
    memset(s,0,sizeof(*s));demo_init(&s->link,8);s->signature=0x4d545234u;
    s->state=FC_STARTUP;s->boot_ms=now;s->last_bus_ms=now;
}
void fc_command(FreeControl *s,const uint8_t in[32],uint32_t now,uint8_t out[32]) {
    int16_t old_yaw=s->link.yaw,old_pitch=s->link.pitch;
    uint16_t target;unsigned axis;
    uint32_t seq=(uint32_t)in[4]|((uint32_t)in[5]<<8)|((uint32_t)in[6]<<16)|((uint32_t)in[7]<<24);
    demo_command(&s->link,in,now,out);
    if(s->link.result==DEMO_OK && in[3]==3) fc_stop(s,now);
    if(s->state!=FC_READY && s->link.armed) {disarm(s);s->link.result=DEMO_DISARMED;}
    if(!s->link.armed) s->pose_axis=0;
    if(s->link.result==DEMO_OK && in[3]==2) {
        for(axis=0;axis<2;axis++) {
            if(!fc_target_raw(axis,axis?s->link.pitch:s->link.yaw,&target) ||
               target<s->configured_min[axis]+16u || target+16u>s->configured_max[axis]) {
                s->link.yaw=old_yaw;s->link.pitch=old_pitch;disarm(s);s->link.result=DEMO_RANGE;break;
            }
        }
        if(s->link.result==DEMO_OK)s->pose_axis=1;
    }
    demo_status(&s->link,seq,now,out);
}
static size_t read_request(FreeControl *s,unsigned axis,uint8_t address,uint8_t count,uint32_t now,uint8_t out[11]) {
    unsigned sum;out[0]=out[1]=255;out[2]=(uint8_t)(axis+1);out[3]=4;out[4]=2;out[5]=address;out[6]=count;
    sum=out[2]+out[3]+out[4]+out[5]+out[6];out[7]=(uint8_t)~sum;
    s->pending=1;s->pending_axis=(uint8_t)axis;s->pending_address=address;s->pending_count=count;s->pending_ms=now;
    s->last_bus_ms=now;s->tx_reads++;return 8;
}
static size_t move_request(FreeControl *s,unsigned axis,uint16_t target,uint16_t ms,uint32_t now,uint8_t out[11]) {
    if(axis>1 || target<soft_minimum[axis] || target>soft_maximum[axis] ||
       target<s->configured_min[axis]+16u || target+16u>s->configured_max[axis] || ms<100 || ms>1500) {fault(s);return 0;}
    s->last_bus_ms=now;s->tx_moves++;return joho_move((uint8_t)(axis+1),target,ms,out);
}
static void response(FreeControl *s,const uint8_t *p,size_t n,uint32_t now) {
    size_t i;unsigned sum=0,axis=s->pending_axis;uint16_t value;
    /* Ignore six-byte write ACKs. Only a matching timely READ can update raw. */
    if(!s->pending || p[2]!=axis+1 || n!=(size_t)s->pending_count+6u) return;
    if((uint32_t)(now-s->pending_ms)>=80u) {read_timeout(s,now);return;}
    for(i=2;i<n;i++) sum+=p[i];
    if((sum&255u)!=255u || p[4]) {s->link.bus_status=p[4];fault(s);return;}
    s->link.bus_status=0;s->pending=0;value=s->pending_count==1?p[5]:be16(p+5);
    if(s->state==FC_CONFIG_LIMIT) {
        uint16_t upper=be16(p+7);
        if(axis!=1 || s->pending_count!=4 || s->pending_address!=0x09) {fault(s);return;}
        if(s->limit_phase==0 && value==1300 && upper==3190) {s->limit_phase=1;return;}
        if(value==400 && upper==3550 && (s->limit_phase==0 || s->limit_phase==2)) {
            s->configured_min[1]=value;s->configured_max[1]=upper;
            s->limit_result=s->limit_phase==0?3u:2u;s->limit_phase=3;s->state=FC_READY;
            disarm(s);s->link.result=DEMO_DISARMED;s->link.seen_feedback[0]=s->link.seen_feedback[1]=0;
            s->last_poll_ms=now-100u;return;
        }
        fault(s);return;
    }
    if(s->state==FC_STARTUP) {
        unsigned step=s->preflight%4u;
        if((step<2 && value!=1) || (step==2 &&
           ((axis==0 && (value!=610 || be16(p+7)!=3550)) ||
            (axis==1 && !((value==1300 && be16(p+7)==3190) || (value==400 && be16(p+7)==3550))))) ||
           (step==3 && (value<soft_minimum[axis] || value>soft_maximum[axis]))) {fault(s);return;}
        if(step==2) {s->configured_min[axis]=value;s->configured_max[axis]=be16(p+7);}
        if(step==3) {s->link.raw[axis]=value;s->link.seen_feedback[axis]=1;s->link.feedback_ms[axis]=now;}
        if(++s->preflight==8) {s->state=FC_HOMING;s->home_axis=0;}
        return;
    }
    if(s->pending_address!=0x38 || value>4095 || value<soft_minimum[axis] || value>soft_maximum[axis]) {fault(s);return;}
    s->link.raw[axis]=value;s->link.seen_feedback[axis]=1;s->link.feedback_ms[axis]=now;
    if(s->state==FC_LINK_WAIT) {
        s->recovery_mask|=(uint8_t)(1u<<axis);
        if(s->recovery_mask==3 && s->link.seen_feedback[0] && s->link.seen_feedback[1] &&
           (uint32_t)(now-s->link.feedback_ms[0])<=1000u && (uint32_t)(now-s->link.feedback_ms[1])<=1000u) {
            s->state=FC_READY;s->recoveries++;
            disarm(s);s->link.result=DEMO_DISARMED;s->last_poll_ms=now;
        }
    }
    if(s->state==FC_HOMING && s->home_baseline<2 && !s->home_read) {
        if(!s->home_baseline) {s->home_baseline_first=value;s->home_baseline_ms=now;s->home_baseline=1;}
        else if(gap(value,s->home_baseline_first)>4) fault(s);
        else s->home_baseline=2;
    }
    if(s->state==FC_HOMING && s->home_read) {
        s->home_read=s->home_wait=0;
        if(gap(value,s->pending_origin)>288 ||
           ((s->home_target>s->pending_origin && value+8<s->pending_origin) ||
            (s->home_target<s->pending_origin && value>s->pending_origin+8)) ||
           (gap(value,s->home_target)>32 && gap(value,s->pending_origin)<128)) fault(s);
    }
}
void fc_byte(FreeControl *s,uint8_t byte,uint32_t now) {
    if(s->used && (uint32_t)(now-s->last_bus_ms)>20u) s->used=0;
    s->last_bus_ms=now;
    if(!s->used && byte!=255) return;
    if(s->used==1 && byte!=245) {s->used=byte==255?1u:0u;return;}
    s->rx[s->used++]=byte;
    if(s->used==4 && (s->rx[3]<2 || s->rx[3]>10)) {s->used=0;fault(s);return;}
    if(s->used>=4 && s->used==s->rx[3]+4u) {response(s,s->rx,s->used,now);s->used=0;}
}
size_t fc_poll(FreeControl *s,uint32_t now,uint8_t out[18]) {
    uint16_t target;unsigned axis;
    demo_tick(&s->link,now);
    if(!s->link.armed) {s->pose_axis=0;s->link.pose_pending=0;}
    if(s->pending && (uint32_t)(now-s->pending_ms)>=80u) {read_timeout(s,now);return 0;}
    if(s->state==FC_FAULT || s->pending || (uint32_t)(now-s->last_bus_ms)<20u) return 0;
    if(s->state==FC_STARTUP) {
        static const uint8_t address[4]={0x1c,0x28,0x09,0x38},count[4]={1,1,4,2};
        if((uint32_t)(now-s->boot_ms)<3000u) return 0;
        if(free_saved_reference[0]!=0x47524331 || free_saved_reference[1]!=1 ||
           free_saved_reference[2]!=2088 || free_saved_reference[3]!=1961) {fault(s);return 0;}
        return read_request(s,s->preflight/4,address[s->preflight%4],count[s->preflight%4],now,out);
    }
    if(s->state==FC_CONFIG_LIMIT) {
        unsigned i,sum=0;
        if(s->limit_phase==0 || s->limit_phase==2)return read_request(s,1,0x09,4,now,out);
        if(s->limit_phase!=1 || s->limit_writes) {fault(s);return 0;}
        /* Exactly one persistent ID2 position-limit WRITE, no motor command.
         * Old pair must have been read as1300/3190; new pair400/3550 leaves
         * margin around calibrated+/-90deg within the human-cleared sweep. */
        out[0]=out[1]=255;out[2]=2;out[3]=7;out[4]=3;out[5]=0x09;
        out[6]=1;out[7]=0x90;out[8]=0x0d;out[9]=0xde;
        for(i=2;i<10;i++)sum+=out[i];out[10]=(uint8_t)~sum;
        s->limit_writes=1;s->limit_phase=2;s->last_bus_ms=now;return 11;
    }
    if(s->state==FC_HOMING) {
        if(s->home_wait) {
            if((uint32_t)(now-s->settle_ms)<1600u) return 0;
            s->home_read=1;return read_request(s,s->home_axis,0x38,2,now,out);
        }
        axis=s->home_axis;target=(uint16_t)free_saved_reference[axis+2];
        if(s->home_baseline<2) {
            if(s->home_baseline==1 && (uint32_t)(now-s->home_baseline_ms)<100u) return 0;
            return read_request(s,axis,0x38,2,now,out);
        }
        if(gap(s->link.raw[axis],target)<=32) {
            if(axis==0) {s->home_axis=1;s->home_moves=0;s->home_baseline=0;return 0;}
            s->state=FC_READY;s->last_poll_ms=now;return 0;
        }
        if(s->home_moves>=6 || !s->link.seen_feedback[axis]) {fault(s);return 0;}
        if((uint32_t)(now-s->link.feedback_ms[axis])>1000u)
            return read_request(s,axis,0x38,2,now,out);
        s->pending_origin=s->link.raw[axis];
        if(gap(s->pending_origin,target)>256) target=(uint16_t)(s->pending_origin>target?s->pending_origin-256:s->pending_origin+256);
        s->home_target=target;s->home_moves++;s->home_wait=1;s->settle_ms=now;
        return move_request(s,axis,target,1500,now,out);
    }
    /* At least5Hz per axis feedback; writes cannot starve overdue reads. */
    if((uint32_t)(now-s->last_poll_ms)>=(s->state==FC_LINK_WAIT?200u:100u)) {
        axis=s->poll_axis;s->poll_axis^=1u;s->last_poll_ms=now;
        return read_request(s,axis,0x38,2,now,out);
    }
    if(s->link.armed && s->link.pose_pending && s->pose_axis) {
        uint16_t targets[2];unsigned i,sum=0;
        if(s->link.move_ms<100 || s->link.move_ms>1000) {fault(s);return 0;}
        for(axis=0;axis<2;axis++)
            if(!s->link.seen_feedback[axis] || (uint32_t)(now-s->link.feedback_ms[axis])>1000u ||
               !fc_target_raw(axis,axis?s->link.pitch:s->link.yaw,&targets[axis]) ||
               targets[axis]<s->configured_min[axis]+16u || targets[axis]+16u>s->configured_max[axis]) {fault(s);return 0;}
        /* Vendor protocol2.0.2 section2.3.6: one SYNC WRITE frame contains
         * only IDs1 and2, target position+finite runtime. No scan, configuration
         * write, deferred ACTION buffer or generic broadcast WRITE is used. */
        out[0]=out[1]=255;out[2]=254;out[3]=14;out[4]=0x83;out[5]=0x2a;out[6]=4;
        for(axis=0;axis<2;axis++) {
            i=7+axis*5;out[i]=(uint8_t)(axis+1);
            out[i+1]=(uint8_t)(targets[axis]>>8);out[i+2]=(uint8_t)targets[axis];
            out[i+3]=(uint8_t)(s->link.move_ms>>8);out[i+4]=(uint8_t)s->link.move_ms;
        }
        for(i=2;i<17;i++)sum+=out[i];out[17]=(uint8_t)~sum;
        s->pose_axis=0;s->link.pose_pending=0;s->tx_moves+=2;s->sync_frames++;s->last_bus_ms=now;
        return 18;
    }
    return 0;
}
