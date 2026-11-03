/* Independent display controller. No product-world or sensor-truth inputs. */
#include "demo_core.h"
#include <string.h>
static uint16_t u16(const uint8_t *p) { return (uint16_t)(p[0] | ((uint16_t)p[1]<<8)); }
static uint32_t u32(const uint8_t *p) { return (uint32_t)u16(p) | ((uint32_t)u16(p+2)<<16); }
static void w16(uint8_t *p, uint16_t v) { p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8); }
static void w32(uint8_t *p, uint32_t v) { w16(p,(uint16_t)v); w16(p+2,(uint16_t)(v>>16)); }
uint16_t demo_crc(const uint8_t *p, size_t n) {
    uint16_t c=0xffff; size_t i; unsigned k;
    for(i=0;i<n;i++) { c^=(uint16_t)p[i]<<8;
        for(k=0;k<8;k++) c=(uint16_t)((c&0x8000)?(c<<1)^0x1021:c<<1);
    } return c;
}
void demo_init(Demo *s, uint8_t capabilities) {
    memset(s,0,sizeof(*s)); s->capabilities=capabilities & 12u;
    s->raw[0]=s->raw[1]=0xffff; s->bus_status=0xff;
}
static void stop(Demo *s, uint32_t now) {
    if(s->duty) s->stopped_ms=now;
    s->armed=0; s->duty=0; s->pose_pending=0;
}
void demo_bus_error(Demo *s) { if(s->bus_errors<65535) s->bus_errors++; }
void demo_tick(Demo *s, uint32_t now) {
    if(s->armed && (uint32_t)(now-s->last_set_ms)>=DEMO_WATCHDOG_MS) {
        stop(s,now); s->result=DEMO_WATCHDOG;
    }
    if(s->pending_read_id && (uint32_t)(now-s->pending_read_ms)>=80u) {
        s->pending_read_id=0; demo_bus_error(s);
    }
}
static uint16_t age(Demo *s, unsigned axis, uint32_t now) {
    uint32_t a=now-s->feedback_ms[axis];
    return s->seen_feedback[axis]?(a>65534?65534:(uint16_t)a):65535;
}
void demo_status(Demo *s, uint32_t seq, uint32_t now, uint8_t *out) {
    unsigned i; memset(out,0,32); out[0]=0xd3; out[1]=0x4c; out[2]=1; out[3]=0x80;
    w32(out+4,seq); out[8]=s->armed; out[9]=s->result;
    w16(out+10,(uint16_t)s->yaw); w16(out+12,(uint16_t)s->pitch); w16(out+14,s->duty);
    out[16]=s->direction; out[17]=s->source; out[18]=s->capabilities; out[19]=s->bus_status;
    for(i=0;i<2;i++) {
        uint16_t a=age(s,i,now); w16(out+20+2*i,s->raw[i]); w16(out+24+2*i,a);
        if(s->seen_feedback[i] && a<=1000 && s->bus_status==0) out[18]|=(uint8_t)(1u<<i);
    } w16(out+28,s->bus_errors); w16(out+30,demo_crc(out,30));
}
void demo_command(Demo *s, const uint8_t *p, uint32_t now, uint8_t *out) {
    uint32_t seq=u32(p+4); uint8_t op=p[3], source=p[8];
    int16_t y=(int16_t)u16(p+10), t=(int16_t)u16(p+12);
    uint16_t d=u16(p+14), ms=u16(p+18); unsigned i;
    demo_tick(s,now);
    if(demo_crc(p,30)!=u16(p+30)) { s->result=DEMO_CRC; goto reply; }
    if(p[0]!=0xd3 || p[1]!=0x4c || p[2]!=1 || op<1 || op>4 ||
       source<1 || source>3 || p[9] || p[17] || p[28] || p[29]) {
        s->result=DEMO_FORMAT; goto reply;
    }
    if(op!=2) for(i=10;i<28;i++) if(p[i]) { s->result=DEMO_FORMAT; goto reply; }
    /* A valid STOP always removes drive, even if its sequence is old. */
    if(op==3) {
        stop(s,now); if(!s->have_seq || seq>s->last_seq) { s->last_seq=seq; s->have_seq=1; }
        s->result=DEMO_OK; goto reply;
    }
    if(s->have_seq && seq<=s->last_seq) { s->result=DEMO_SEQUENCE; goto reply; }
    s->last_seq=seq; s->have_seq=1;
    if(op==4) goto reply;
    if(op==1) {
        if(s->armed && source!=s->source) { s->result=DEMO_SOURCE; goto reply; }
        if(!s->armed) { s->source=source; s->last_set_ms=now; s->armed=1; }
        s->result=DEMO_OK; goto reply;
    }
    if(!s->armed) { s->result=DEMO_DISARMED; goto reply; }
    if(source!=s->source) { s->result=DEMO_SOURCE; goto reply; }
    if(y < -DEMO_YAW_BOUND_CDEG || y>DEMO_YAW_BOUND_CDEG ||
       t < -DEMO_PITCH_BOUND_CDEG || t>DEMO_PITCH_BOUND_CDEG ||
       d>300 || (DEMO_GIMBAL_ONLY && (d || p[16])) || p[16]>1 || ms<100 || ms>1000) {
        s->result=DEMO_RANGE; goto reply;
    }
    if(p[16]!=s->direction && (s->duty || (uint32_t)(now-s->stopped_ms)<DEMO_REVERSE_MS)) {
        s->result=DEMO_REVERSE_WAIT; goto reply;
    }
    if(s->duty && !d) s->stopped_ms=now;
    s->duty=d; s->direction=p[16]; s->yaw=y; s->pitch=t; s->move_ms=ms;
    s->pose_pending=1; s->last_set_ms=now; s->result=DEMO_OK;
reply: demo_status(s,seq,now,out);
}
static void checksum(uint8_t *p, size_t n) {
    unsigned sum=0; size_t i; for(i=2;i<n-1;i++) sum+=p[i]; p[n-1]=(uint8_t)~sum;
}
size_t joho_move(uint8_t id, uint16_t position, uint16_t ms, uint8_t *out) {
    if(id<1 || id>250 || position>4095) return 0;
    out[0]=out[1]=0xff; out[2]=id; out[3]=7; out[4]=3; out[5]=0x2a;
    out[6]=(uint8_t)(position>>8); out[7]=(uint8_t)position;
    out[8]=(uint8_t)(ms>>8); out[9]=(uint8_t)ms; checksum(out,11); return 11;
}
size_t joho_read(uint8_t id, uint8_t *out) {
    if(id<1 || id>250) return 0;
    out[0]=out[1]=0xff; out[2]=id; out[3]=4; out[4]=2; out[5]=0x38; out[6]=2;
    checksum(out,8); return 8;
}
void demo_begin_read(Demo *s, uint8_t id, uint32_t now) { s->pending_read_id=id; s->pending_read_ms=now; }
int demo_bus_response(Demo *s, const uint8_t *p, size_t n, uint32_t now) {
    size_t i; unsigned sum=0,axis; uint16_t raw;
    if(n!=8 || p[0]!=0xff || p[1]!=0xf5 || p[3]!=4) { demo_bus_error(s); return 0; }
    for(i=2;i<n;i++) sum+=p[i];
    if((sum&255u)!=255u) { demo_bus_error(s); return 0; }
    if(!s->pending_read_id || p[2]!=s->pending_read_id || (uint32_t)(now-s->pending_read_ms)>=80u) {
        demo_bus_error(s); return 0;
    }
    s->pending_read_id=0; s->bus_status=p[4];
    if(p[2]<1 || p[2]>2 || p[4]) { demo_bus_error(s); return 0; }
    raw=(uint16_t)(((uint16_t)p[5]<<8)|p[6]);
    if(raw>4095) { demo_bus_error(s); return 0; }
    axis=p[2]-1u; s->raw[axis]=raw; s->seen_feedback[axis]=1; s->feedback_ms[axis]=now; return 1;
}
