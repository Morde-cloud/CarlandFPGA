#include "motor_control.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned checks;
#define CHECK(c) do{checks++;if(!(c)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#c);exit(1);}}while(0)
static void w16(uint8_t *p,uint16_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void w32(uint8_t *p,uint32_t v){w16(p,(uint16_t)v);w16(p+2,(uint16_t)(v>>16));}
static void seal(uint8_t *f){w16(f+30,demo_crc(f,30));}
static void base(uint8_t *f,uint8_t op,uint32_t seq,uint8_t source){memset(f,0,32);f[0]=0xd3;f[1]=0x4c;f[2]=1;f[3]=op;w32(f+4,seq);f[8]=source;}
static void delta(uint8_t *f,uint32_t seq,uint32_t cmd,uint32_t run,int16_t y,int16_t p,int16_t speed,uint8_t flags){base(f,6,seq,1);f[9]=flags;w16(f+10,(uint16_t)y);w16(f+12,(uint16_t)p);w16(f+14,(uint16_t)speed);w16(f+18,500);w32(f+20,cmd);w32(f+24,run);w16(f+28,300);seal(f);}
static void heartbeat(uint8_t *f,uint32_t seq,uint32_t cmd,uint32_t run){base(f,7,seq,1);f[9]=1;w32(f+20,cmd);w32(f+24,run);w16(f+28,300);seal(f);}
static void ready(MotorRuntime *m,FreeControl *g){fc_init(g,1000);mc_init(m);g->state=FC_READY;g->link.bus_status=0;g->link.seen_feedback[0]=g->link.seen_feedback[1]=1;g->link.feedback_ms[0]=g->link.feedback_ms[1]=1000;g->link.raw[0]=2088;g->link.raw[1]=1961;g->configured_min[0]=610;g->configured_min[1]=400;g->configured_max[0]=g->configured_max[1]=3550;}
static void arm(MotorRuntime *m,FreeControl *g,uint32_t seq,uint32_t now){uint8_t f[32],o[32];base(f,1,seq,1);seal(f);mc_command(m,g,f,now,o);CHECK(g->link.result==DEMO_OK&&g->link.armed&&m->duty==0);}
int main(int argc,char **argv){MotorRuntime m;FreeControl g;uint8_t f[32],o[32];int16_t y,p;
 ready(&m,&g);arm(&m,&g,1,1000);delta(f,2,1,7,100,-200,100,1);mc_command(&m,&g,f,1001,o);
 CHECK(g.link.result==DEMO_OK&&g.link.yaw==100&&g.link.pitch==-200&&m.duty==300&&m.speed_norm==100&&g.link.pose_pending&&m.command_seq==1);
 mc_command(&m,&g,f,1002,o);CHECK(g.link.result==DEMO_SEQUENCE&&g.link.yaw==100&&g.link.pitch==-200&&!g.link.armed&&m.duty==0);
 arm(&m,&g,3,1003);delta(f,4,1,7,100,-200,100,1);mc_command(&m,&g,f,1004,o);CHECK(g.link.result==DEMO_SEQUENCE&&g.link.yaw==100&&g.link.pitch==-200);
 arm(&m,&g,5,1005);delta(f,6,2,7,200,300,100,1);mc_command(&m,&g,f,1006,o);CHECK(g.link.result==DEMO_OK&&g.link.yaw==300&&g.link.pitch==100&&m.duty==300);
 delta(f,7,3,7,100,100,100,1);f[8]=2;seal(f);mc_command(&m,&g,f,1007,o);CHECK(g.link.result==DEMO_SOURCE&&g.link.yaw==300&&g.link.pitch==100&&m.duty==0);
 arm(&m,&g,8,1008);delta(f,9,3,7,32767,32767,32767,1);mc_command(&m,&g,f,1009,o);CHECK(g.link.result==DEMO_OK&&g.link.yaw==9000&&g.link.pitch==6800&&m.speed_norm==1000&&m.duty==750);
 delta(f,10,4,7,-32768,-32768,-32768,1);mc_command(&m,&g,f,1010,o);CHECK(g.link.result==DEMO_OK&&g.link.yaw==-9000&&g.link.pitch==-4500&&m.duty==0&&g.link.armed);
 delta(f,11,5,7,100,100,100,1);f[30]^=1;mc_command(&m,&g,f,1011,o);CHECK(g.link.result==DEMO_CRC&&g.link.yaw==-9000&&g.link.pitch==-4500&&!g.link.armed&&m.command_seq==4);
 arm(&m,&g,11,1012);delta(f,12,5,7,0,0,0,3);mc_command(&m,&g,f,1013,o);CHECK(g.link.result==DEMO_OK&&!g.link.armed&&!g.link.pose_pending&&m.duty==0&&m.command_seq==5);
 delta(f,13,1,8,100,100,100,1);mc_command(&m,&g,f,1014,o);CHECK(g.link.result==DEMO_SEQUENCE&&m.run_id==7&&m.command_seq==5);
 arm(&m,&g,14,1015);delta(f,15,1,8,100,100,100,1);mc_command(&m,&g,f,1016,o);CHECK(g.link.result==DEMO_OK&&m.run_id==8&&m.command_seq==1&&m.duty==300);
 y=g.link.yaw;p=g.link.pitch;delta(f,16,1,9,100,100,100,1);mc_command(&m,&g,f,1017,o);CHECK(g.link.result==DEMO_SEQUENCE&&m.run_id==8&&g.link.yaw==y&&g.link.pitch==p&&m.duty==0);
 arm(&m,&g,17,1100);delta(f,18,2,8,100,100,200,1);w16(f+28,100);seal(f);mc_command(&m,&g,f,1101,o);CHECK(m.duty==350&&g.link.armed);mc_tick(&m,&g,1201);CHECK(m.duty==0&&!g.link.armed);
 arm(&m,&g,19,1300);delta(f,20,3,8,100,100,100,1);mc_command(&m,&g,f,1301,o);CHECK(m.duty==300);g.link.seen_feedback[1]=0;mc_tick(&m,&g,1302);CHECK(m.duty==0&&!g.link.armed);
 ready(&m,&g);g.configured_min[1]=1300;g.configured_max[1]=3190;arm(&m,&g,1,1000);delta(f,2,1,1,0,-32768,0,1);mc_command(&m,&g,f,1001,o);{uint16_t raw=0;CHECK(g.link.result==DEMO_OK&&g.link.pitch>-4500&&g.link.pitch<0&&fc_target_raw(1,g.link.pitch,&raw)&&raw>=1316);}
 ready(&m,&g);arm(&m,&g,1,1000);g.configured_min[1]=2000;delta(f,2,1,1,100,100,100,1);mc_command(&m,&g,f,1001,o);CHECK(g.link.result==DEMO_RANGE&&g.link.yaw==0&&g.link.pitch==0&&m.command_seq==0&&m.duty==0);
 ready(&m,&g);arm(&m,&g,1,1000);delta(f,2,1,1,1,0,0,3);mc_command(&m,&g,f,1001,o);CHECK(g.link.result==DEMO_FORMAT&&!g.link.armed&&g.link.yaw==0);
 ready(&m,&g);arm(&m,&g,1,1000);delta(f,2,1,1,100,-200,100,1);mc_command(&m,&g,f,1001,o);heartbeat(f,3,1,1);mc_command(&m,&g,f,1100,o);CHECK(g.link.result==DEMO_OK&&m.commands==1&&m.command_seq==1&&g.link.yaw==100&&g.link.pitch==-200&&m.speed_norm==100&&m.duty==300&&m.deadline_ms==1400);
 heartbeat(f,4,2,1);mc_command(&m,&g,f,1101,o);CHECK(g.link.result==DEMO_SEQUENCE&&m.command_seq==1&&m.commands==1&&m.duty==0&&!g.link.armed);
 arm(&m,&g,5,1102);heartbeat(f,6,1,1);mc_command(&m,&g,f,1103,o);CHECK(g.link.result==DEMO_DISARMED&&m.duty==0&&!g.link.armed);
 arm(&m,&g,7,1104);delta(f,8,2,1,10,20,200,1);mc_command(&m,&g,f,1105,o);heartbeat(f,9,2,1);mc_command(&m,&g,f,1405,o);CHECK(g.link.result==DEMO_DISARMED&&m.command_seq==2&&m.commands==2&&m.duty==0&&!g.link.armed);
 if(argc==2){FILE *in=NULL;size_t n;CHECK(fopen_s(&in,argv[1],"rb")==0&&in);n=fread(f,1,32,in);fclose(in);CHECK(n==32);ready(&m,&g);arm(&m,&g,1,1000);mc_command(&m,&g,f,1001,o);CHECK(g.link.result==DEMO_OK&&g.link.yaw==100&&g.link.pitch==-200&&m.duty==300);printf("PYTHON_FRAME_ACCEPTED yaw=%d pitch=%d duty=%u\n",g.link.yaw,g.link.pitch,(unsigned)m.duty);}
 printf("DELTA_INVARIANTS_PASS checks=%u MotorRuntime_size=%u FreeControl_size=%u\n",checks,(unsigned)sizeof(m),(unsigned)sizeof(g));return 0;
}
