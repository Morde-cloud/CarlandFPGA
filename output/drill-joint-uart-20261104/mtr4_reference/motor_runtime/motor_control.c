#include "motor_control.h"
#include <string.h>
static uint16_t u16(const uint8_t *p){return (uint16_t)(p[0]|((uint16_t)p[1]<<8));}
static uint32_t u32(const uint8_t *p){return (uint32_t)u16(p)|((uint32_t)u16(p+2)<<16);}
static void stop_motor(MotorRuntime *m){if(m->active || m->duty)m->stops++;m->active=0;m->duty=0;}
static int healthy(const FreeControl *g,uint32_t now){
    return g->state==FC_READY && g->link.bus_status==0 &&
        g->link.seen_feedback[0] && g->link.seen_feedback[1] &&
        (uint32_t)(now-g->link.feedback_ms[0])<=1000u &&
        (uint32_t)(now-g->link.feedback_ms[1])<=1000u;
}
void mc_init(MotorRuntime *m){memset(m,0,sizeof(*m));}
void mc_tick(MotorRuntime *m,FreeControl *g,uint32_t now){
    demo_tick(&g->link,now);
    if(m->active && (!g->link.armed || !healthy(g,now) || (int32_t)(now-m->deadline_ms)>=0)){
        stop_motor(m);fc_stop(g,now);g->link.result=DEMO_WATCHDOG;
    }
}
static void status(MotorRuntime *m,FreeControl *g,uint32_t seq,uint32_t now,uint8_t out[32]){
    uint16_t crc;demo_status(&g->link,seq,now,out);
    out[14]=(uint8_t)m->duty;out[15]=(uint8_t)(m->duty>>8);
    out[18]|=4u; /* Motor output is compiled, even when commanded duty is zero. */
    crc=demo_crc(out,30);out[30]=(uint8_t)crc;out[31]=(uint8_t)(crc>>8);
}
void mc_command(MotorRuntime *m,FreeControl *g,const uint8_t in[32],uint32_t now,uint8_t out[32]){
    uint32_t seq=u32(in+4);unsigned i;uint16_t duty=u16(in+14),lease=u16(in+18);
    mc_tick(m,g,now);
    if(in[3]!=5){
        fc_command(g,in,now,out);
        if(g->link.result!=DEMO_OK || in[3]==3){stop_motor(m);fc_stop(g,now);}
        mc_tick(m,g,now);status(m,g,seq,now,out);return;
    }
    if(demo_crc(in,30)!=u16(in+30)){g->link.result=DEMO_CRC;goto fail;}
    if(in[0]!=0xd3 || in[1]!=0x4c || in[2]!=1 || in[8]<1 || in[8]>3 ||
       in[9] || in[16] || in[17] || in[28] || in[29]){g->link.result=DEMO_FORMAT;goto fail;}
    for(i=10;i<14;i++)if(in[i]){g->link.result=DEMO_FORMAT;goto fail;}
    for(i=20;i<28;i++)if(in[i]){g->link.result=DEMO_FORMAT;goto fail;}
    if(g->link.have_seq && seq<=g->link.last_seq){g->link.result=DEMO_SEQUENCE;goto fail;}
    g->link.last_seq=seq;g->link.have_seq=1;
    if((duty && duty<250) || duty>750 || lease<100 || lease>500){g->link.result=DEMO_RANGE;goto fail;}
    if(!g->link.armed || !healthy(g,now)){g->link.result=DEMO_DISARMED;goto fail;}
    if(in[8]!=g->link.source){g->link.result=DEMO_SOURCE;goto fail;}
    m->commands++;m->duty=duty;m->active=(uint8_t)(duty!=0);m->deadline_ms=now+lease;
    g->link.last_set_ms=now;g->link.result=DEMO_OK;
    if(!duty)fc_stop(g,now);
    status(m,g,seq,now,out);return;
fail:
    stop_motor(m);fc_stop(g,now);status(m,g,seq,now,out);
}
