#include "motor_control.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned checks;
#define CHECK(c) do{checks++;if(!(c)){fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#c);exit(1);}}while(0)
static void w16(uint8_t *p,uint16_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void w32(uint8_t *p,uint32_t v){w16(p,(uint16_t)v);w16(p+2,(uint16_t)(v>>16));}
static void seal(uint8_t *f){w16(f+30,demo_crc(f,30));}
static void frame(uint8_t *f,uint8_t op,uint32_t seq){memset(f,0,32);f[0]=0xd3;f[1]=0x4c;f[2]=1;f[3]=op;w32(f+4,seq);f[8]=2;}
static void prepare(uint8_t *f,uint32_t seq,uint32_t run,uint16_t speed){frame(f,8,seq);f[9]=1;w16(f+14,speed);w16(f+18,500);w32(f+24,run);seal(f);}
static void ready(MotorRuntime *m,FreeControl *g){fc_init(g,1000);mc_init(m);g->state=FC_READY;g->link.bus_status=0;g->link.seen_feedback[0]=g->link.seen_feedback[1]=1;g->link.feedback_ms[0]=g->link.feedback_ms[1]=1000;g->link.raw[0]=2216;g->link.raw[1]=2097;g->configured_min[0]=610;g->configured_min[1]=400;g->configured_max[0]=g->configured_max[1]=3550;g->last_poll_ms=1000;g->last_bus_ms=980;g->link.yaw=950;g->link.pitch=949;}
int main(int argc,char **argv){MotorRuntime m;FreeControl g;uint8_t f[32],o[32],bus[18];unsigned sum=0,i;size_t n;
 ready(&m,&g);prepare(f,302,1793772501,880);mc_command(&m,&g,f,1000,o);
 CHECK(g.link.result==DEMO_OK&&!g.link.armed&&!m.active&&!m.duty&&!m.speed_norm);
 CHECK(m.prepared_valid&&m.prepared_run_id==1793772501&&m.prepared_speed_permille==880&&m.prepared_source==2);
 CHECK(g.link.yaw==0&&g.link.pitch==0&&g.startup_pose_pending&&!g.link.pose_pending&&m.commands==0&&!m.delta_live&&!m.have_run);
 CHECK(o[8]==0&&o[9]==0&&o[14]==0&&o[15]==0&&g.link.raw[0]==2216&&g.link.raw[1]==2097);
 CHECK(g.link.last_set_ms==0&&m.deadline_ms==0&&g.link.move_ms==500);
 n=fc_poll(&g,1000,bus);CHECK(n==18&&bus[2]==254&&bus[4]==0x83&&bus[7]==1&&bus[12]==2);
 CHECK(bus[8]==(2088>>8)&&bus[9]==(2088&255)&&bus[13]==(1961>>8)&&bus[14]==(1961&255));
 CHECK(bus[10]==1&&bus[11]==244&&bus[15]==1&&bus[16]==244);
 for(i=2;i<18;i++)sum+=bus[i];CHECK((sum&255)==255&&!g.startup_pose_pending&&g.tx_moves==2);
 CHECK(fc_poll(&g,1020,bus)==0&&g.tx_moves==2); /* one-shot, no ARM */
 frame(f,1,303);seal(f);mc_command(&m,&g,f,1020,o);CHECK(g.link.armed&&m.prepared_valid&&!m.duty&&!m.speed_norm&&g.tx_moves==2);
 frame(f,6,304);f[9]=1;w16(f+14,880);w16(f+18,500);w32(f+20,1);w32(f+24,1793772501);w16(f+28,300);seal(f);mc_command(&m,&g,f,1021,o);
 CHECK(g.link.result==DEMO_OK&&m.speed_norm==880&&m.duty==690&&!m.prepared_valid&&m.commands==1&&m.run_id==1793772501);
 frame(f,3,305);seal(f);mc_command(&m,&g,f,1022,o);CHECK(!g.link.armed&&!m.duty&&!m.prepared_valid&&!g.startup_pose_pending);
 prepare(f,306,1793772501,880);mc_command(&m,&g,f,1023,o);CHECK(g.link.result==DEMO_SEQUENCE&&g.tx_moves==2);
 prepare(f,307,1793772502,0);mc_command(&m,&g,f,1024,o);CHECK(g.link.result==DEMO_OK&&m.prepared_valid&&g.startup_pose_pending&&!m.duty);
 frame(f,3,308);seal(f);mc_command(&m,&g,f,1025,o);CHECK(g.link.result==DEMO_OK&&!m.prepared_valid&&!g.startup_pose_pending&&g.tx_moves==2);
 prepare(f,309,1793772502,880);mc_command(&m,&g,f,1026,o);CHECK(g.link.result==DEMO_SEQUENCE); /* STOP keeps highwater */
 ready(&m,&g);prepare(f,302,1793772501,880);f[30]^=1;mc_command(&m,&g,f,1000,o);CHECK(g.link.result==DEMO_CRC&&!m.prepared_valid&&!g.startup_pose_pending&&g.tx_moves==0);
 prepare(f,303,1793772501,1001);mc_command(&m,&g,f,1000,o);CHECK(g.link.result==DEMO_RANGE&&!m.prepared_valid&&g.link.yaw==950);
 prepare(f,304,1793772501,880);f[20]=1;seal(f);mc_command(&m,&g,f,1000,o);CHECK(g.link.result==DEMO_FORMAT&&!m.prepared_valid);
 prepare(f,305,1793772501,880);g.link.seen_feedback[1]=0;mc_command(&m,&g,f,1000,o);CHECK(g.link.result==DEMO_DISARMED&&!m.prepared_valid&&g.tx_moves==0);
 ready(&m,&g);frame(f,1,301);seal(f);mc_command(&m,&g,f,1000,o);prepare(f,302,1793772501,880);mc_command(&m,&g,f,1001,o);CHECK(g.link.result==DEMO_DISARMED&&!g.link.armed&&!m.prepared_valid);
 ready(&m,&g);prepare(f,302,1793772501,880);mc_command(&m,&g,f,1000,o);mc_stop(&m,&g,1001);CHECK(!m.prepared_valid&&!g.startup_pose_pending&&!m.duty&&g.tx_moves==0); /* button/queue failure */
 ready(&m,&g);prepare(f,302,1793772501,880);mc_command(&m,&g,f,1000,o);mc_tick(&m,&g,2001);CHECK(!m.prepared_valid&&!g.startup_pose_pending&&!m.duty); /* stale feedback cancels */
 if(argc==2){FILE *in=NULL;CHECK(fopen_s(&in,argv[1],"rb")==0&&in);n=fread(f,1,32,in);fclose(in);CHECK(n==32);ready(&m,&g);mc_command(&m,&g,f,1000,o);CHECK(g.link.result==DEMO_OK&&m.prepared_speed_permille==880&&m.prepared_run_id==1793772501&&!m.duty);printf("PYTHON_STARTUP_FRAME_ACCEPTED seq302 run1793772501 preset880 actualPWM0\n");}
 printf("STARTUP_PREPARE_PASS checks=%u MotorRuntime_size=%u FreeControl_size=%u\n",checks,(unsigned)sizeof(m),(unsigned)sizeof(g));return 0;
}
