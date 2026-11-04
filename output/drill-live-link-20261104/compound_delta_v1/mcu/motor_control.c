#include "motor_control.h"
#include <string.h>
static uint16_t u16(const uint8_t *p){return (uint16_t)(p[0]|((uint16_t)p[1]<<8));}
static uint32_t u32(const uint8_t *p){return (uint32_t)u16(p)|((uint32_t)u16(p+2)<<16);}
static int32_t clip(int32_t v,int32_t lo,int32_t hi){return v<lo?lo:v>hi?hi:v;}
static void stop_motor(MotorRuntime *m){if(m->active||m->duty)m->stops++;m->active=0;m->duty=0;m->speed_norm=0;}
static void stop_all(MotorRuntime *m,FreeControl *g,uint32_t now){stop_motor(m);m->allow_new_run=0;m->delta_live=0;m->prepared_valid=0;fc_stop(g,now);}
void mc_stop(MotorRuntime *m,FreeControl *g,uint32_t now){stop_all(m,g,now);}
static int healthy(const FreeControl *g,uint32_t now){
    return g->state==FC_READY&&g->link.bus_status==0&&
        g->link.seen_feedback[0]&&g->link.seen_feedback[1]&&
        (uint32_t)(now-g->link.feedback_ms[0])<=1000u&&
        (uint32_t)(now-g->link.feedback_ms[1])<=1000u;
}
void mc_init(MotorRuntime *m){memset(m,0,sizeof(*m));}
void mc_tick(MotorRuntime *m,FreeControl *g,uint32_t now){
    demo_tick(&g->link,now);
    if(m->prepared_valid && !healthy(g,now)){stop_all(m,g,now);g->link.result=DEMO_DISARMED;}
    if((m->active||m->delta_live)&&(!g->link.armed||!healthy(g,now)||(int32_t)(now-m->deadline_ms)>=0)){
        stop_all(m,g,now);g->link.result=DEMO_WATCHDOG;
    }
    if(!g->link.armed){stop_motor(m);m->allow_new_run=0;m->delta_live=0;}
}
static void status(MotorRuntime *m,FreeControl *g,uint32_t seq,uint32_t now,uint8_t out[32]){
    uint16_t crc;demo_status(&g->link,seq,now,out);
    out[14]=(uint8_t)m->duty;out[15]=(uint8_t)(m->duty>>8);out[18]|=4u;
    crc=demo_crc(out,30);out[30]=(uint8_t)crc;out[31]=(uint8_t)(crc>>8);
}
static int axis_ok(const FreeControl *g,unsigned axis,int16_t angle){
    uint16_t raw;
    return fc_target_raw(axis,angle,&raw)&&raw>=g->configured_min[axis]+16u&&
        (uint32_t)raw+16u<=g->configured_max[axis];
}
static int clipped_axis(const FreeControl *g,unsigned axis,int32_t candidate,int16_t *out){
    int32_t v=clip(candidate,axis?-4500:-9000,axis?6800:9000),lo=0,hi=v<0?-v:v;
    int sign=v<0?-1:1;
    /* Saved zero must itself fit the previously read servo limits. The mapping
     * is monotonic on each side of zero; find the nearest legal command. */
    if(!axis_ok(g,axis,0))return 0;
    while(lo<hi){int32_t mid=(lo+hi+1)/2;
        if(axis_ok(g,axis,(int16_t)(sign*mid)))lo=mid;else hi=mid-1;
    }
    *out=(int16_t)(sign*lo);return 1;
}
static void compound(MotorRuntime *m,FreeControl *g,const uint8_t in[32],uint32_t now){
    uint32_t seq=u32(in+4),cmd=u32(in+20),run=u32(in+24);
    uint16_t move=u16(in+18),lease=u16(in+28),speed,duty;
    int16_t y,p;uint8_t flags=in[9],source=in[8];
    if(demo_crc(in,30)!=u16(in+30)){g->link.result=DEMO_CRC;goto fail;}
    if(in[0]!=0xd3||in[1]!=0x4c||in[2]!=1||source<1||source>3||
       !(flags&MC_VALID)||(flags&~7u)||(flags&6u)==6u||in[16]||in[17]||!seq||!cmd||!run||
       ((flags&6u)&&(u16(in+10)||u16(in+12)||u16(in+14)))){
        g->link.result=DEMO_FORMAT;goto fail;
    }
    if(g->link.have_seq&&seq<=g->link.last_seq){g->link.result=DEMO_SEQUENCE;goto fail;}
    g->link.last_seq=seq;g->link.have_seq=1;
    if(move<100||move>1000||lease<100||lease>500){g->link.result=DEMO_RANGE;goto fail;}
    if(m->have_run){
        if(run<m->run_id||(run==m->run_id&&cmd<=m->command_seq)){
            g->link.result=DEMO_SEQUENCE;goto fail;
        }
        if(run==m->run_id&&source!=m->run_source){g->link.result=DEMO_SOURCE;goto fail;}
        if(run>m->run_id&&!m->allow_new_run){g->link.result=DEMO_SEQUENCE;goto fail;}
    }else if(!m->allow_new_run&&!(flags&6u)){g->link.result=DEMO_DISARMED;goto fail;}
    if(flags&6u){
        stop_all(m,g,now);m->run_id=run;m->command_seq=cmd;
        m->run_source=source;m->have_run=1;g->link.result=DEMO_OK;return;
    }
    if(g->startup_pose_pending){g->link.result=DEMO_DISARMED;goto fail;}
    if(m->prepared_valid && (run!=m->prepared_run_id || source!=m->prepared_source)){
        g->link.result=DEMO_SOURCE;goto fail;
    }
    if(!g->link.armed||!healthy(g,now)){g->link.result=DEMO_DISARMED;goto fail;}
    if(source!=g->link.source){g->link.result=DEMO_SOURCE;goto fail;}
    if((!m->have_run||run>m->run_id)&&(m->active||m->duty||g->link.pose_pending)){
        g->link.result=DEMO_DISARMED;goto fail;
    }
    if(!clipped_axis(g,0,(int32_t)g->link.yaw+(int16_t)u16(in+10),&y)||
       !clipped_axis(g,1,(int32_t)g->link.pitch+(int16_t)u16(in+12),&p)){
        g->link.result=DEMO_RANGE;goto fail;
    }
    speed=(uint16_t)clip((int32_t)m->speed_norm+(int16_t)u16(in+14),0,1000);
    duty=speed?(uint16_t)(250u+(500u*(uint32_t)speed+500u)/1000u):0;
    /* No partial delta accumulation before every field and endpoint is valid. */
    g->link.yaw=y;g->link.pitch=p;g->link.move_ms=move;
    g->link.pose_pending=1;g->pose_axis=1;g->link.last_set_ms=now;
    m->speed_norm=speed;m->duty=duty;m->active=(uint8_t)(duty!=0);
    m->deadline_ms=now+lease;m->commands++;m->run_id=run;m->command_seq=cmd;
    m->run_source=source;m->have_run=1;m->allow_new_run=0;m->delta_live=1;m->prepared_valid=0;g->link.result=DEMO_OK;return;
fail:stop_all(m,g,now);
}
static void keepalive(MotorRuntime *m,FreeControl *g,const uint8_t in[32],uint32_t now){
    uint32_t seq=u32(in+4);uint16_t lease=u16(in+28);unsigned i;
    if(demo_crc(in,30)!=u16(in+30)){g->link.result=DEMO_CRC;goto fail;}
    if(in[0]!=0xd3||in[1]!=0x4c||in[2]!=1||in[8]<1||in[8]>3||in[9]!=MC_VALID||!seq){g->link.result=DEMO_FORMAT;goto fail;}
    for(i=10;i<20;i++)if(in[i]){g->link.result=DEMO_FORMAT;goto fail;}
    if(g->link.have_seq&&seq<=g->link.last_seq){g->link.result=DEMO_SEQUENCE;goto fail;}
    g->link.last_seq=seq;g->link.have_seq=1;
    if(lease<100||lease>500){g->link.result=DEMO_RANGE;goto fail;}
    if(!m->delta_live||!g->link.armed||!healthy(g,now)||(int32_t)(now-m->deadline_ms)>=0){g->link.result=DEMO_DISARMED;goto fail;}
    if(in[8]!=m->run_source||in[8]!=g->link.source){g->link.result=DEMO_SOURCE;goto fail;}
    if(u32(in+20)!=m->command_seq||u32(in+24)!=m->run_id){g->link.result=DEMO_SEQUENCE;goto fail;}
    /* A's service separately gates the original source TTL. This renews only
     * an already-live command: no ARM, delta, new AI round or motor restart. */
    m->deadline_ms=now+lease;g->link.last_set_ms=now;g->link.result=DEMO_OK;return;
fail:stop_all(m,g,now);
}
static void startup_prepare(MotorRuntime *m,FreeControl *g,const uint8_t in[32],uint32_t now){
    uint32_t seq=u32(in+4),run=u32(in+24);uint16_t speed=u16(in+14),move=u16(in+18);unsigned i;
    if(demo_crc(in,30)!=u16(in+30)){g->link.result=DEMO_CRC;goto fail;}
    if(in[0]!=0xd3||in[1]!=0x4c||in[2]!=1||in[8]<1||in[8]>3||in[9]!=MC_VALID||!seq||!run||
       in[16]||in[17]||in[28]||in[29]){g->link.result=DEMO_FORMAT;goto fail;}
    for(i=10;i<14;i++)if(in[i]){g->link.result=DEMO_FORMAT;goto fail;}
    for(i=20;i<24;i++)if(in[i]){g->link.result=DEMO_FORMAT;goto fail;}
    if(g->link.have_seq&&seq<=g->link.last_seq){g->link.result=DEMO_SEQUENCE;goto fail;}
    g->link.last_seq=seq;g->link.have_seq=1;
    if(speed>1000||move<100||move>1000){g->link.result=DEMO_RANGE;goto fail;}
    if(run<=m->prepared_run_id || (m->have_run&&run<=m->run_id)){g->link.result=DEMO_SEQUENCE;goto fail;}
    if(m->active||m->duty||m->delta_live||g->link.armed||!healthy(g,now)){
        g->link.result=DEMO_DISARMED;goto fail;
    }
    if(!fc_startup_prepare(g,move,now)){g->link.result=DEMO_DISARMED;goto fail;}
    m->prepared_run_id=run;m->prepared_speed_permille=speed;m->prepared_source=in[8];m->prepared_valid=1;
    m->speed_norm=0;m->allow_new_run=0;g->link.source=in[8];g->link.result=DEMO_OK;return;
fail:stop_all(m,g,now);
}
void mc_command(MotorRuntime *m,FreeControl *g,const uint8_t in[32],uint32_t now,uint8_t out[32]){
    uint32_t seq=u32(in+4);unsigned i;uint16_t duty=u16(in+14),lease=u16(in+18);
    mc_tick(m,g,now);
    if(in[3]==MC_STARTUP_PREPARE){startup_prepare(m,g,in,now);mc_tick(m,g,now);status(m,g,seq,now,out);return;}
    if(in[3]==MC_KEEPALIVE){keepalive(m,g,in,now);mc_tick(m,g,now);status(m,g,seq,now,out);return;}
    if(in[3]==MC_DELTA){compound(m,g,in,now);mc_tick(m,g,now);status(m,g,seq,now,out);return;}
    if(in[3]==2||in[3]==5)m->delta_live=0;
    if(in[3]!=5){
        uint8_t was_armed=g->link.armed;
        fc_command(g,in,now,out);
        if(g->link.result!=DEMO_OK||in[3]==3)stop_all(m,g,now);
        else if(in[3]==1&&!was_armed&&g->link.armed&&!m->active&&!m->duty)m->allow_new_run=1;
        mc_tick(m,g,now);status(m,g,seq,now,out);return;
    }
    if(demo_crc(in,30)!=u16(in+30)){g->link.result=DEMO_CRC;goto fail;}
    if(in[0]!=0xd3||in[1]!=0x4c||in[2]!=1||in[8]<1||in[8]>3||in[9]||in[16]||in[17]||in[28]||in[29]){
        g->link.result=DEMO_FORMAT;goto fail;
    }
    for(i=10;i<14;i++)if(in[i]){g->link.result=DEMO_FORMAT;goto fail;}
    for(i=20;i<28;i++)if(in[i]){g->link.result=DEMO_FORMAT;goto fail;}
    if(g->link.have_seq&&seq<=g->link.last_seq){g->link.result=DEMO_SEQUENCE;goto fail;}
    g->link.last_seq=seq;g->link.have_seq=1;
    if((duty&&duty<250)||duty>750||lease<100||lease>500){g->link.result=DEMO_RANGE;goto fail;}
    if(!g->link.armed||!healthy(g,now)){g->link.result=DEMO_DISARMED;goto fail;}
    if(in[8]!=g->link.source){g->link.result=DEMO_SOURCE;goto fail;}
    m->commands++;m->duty=duty;m->speed_norm=duty>250?(uint16_t)((duty-250u)*2u):0;
    m->active=(uint8_t)(duty!=0);m->deadline_ms=now+lease;
    g->link.last_set_ms=now;g->link.result=DEMO_OK;if(!duty)stop_all(m,g,now);
    status(m,g,seq,now,out);return;
fail:stop_all(m,g,now);status(m,g,seq,now,out);
}
