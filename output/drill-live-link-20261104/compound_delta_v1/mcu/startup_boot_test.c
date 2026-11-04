#include "free_control.h"
#include <stdio.h>
#include <stdlib.h>
#define CHECK(c) do{if(!(c)){fprintf(stderr,"BOOT FAIL line %d\n",__LINE__);exit(1);}}while(0)
int main(void){FreeControl g;uint8_t request[18],reply[10];unsigned step,i,count,sum,axis,value;uint32_t now;
 fc_init(&g,0);
 for(step=0;step<8;step++){
  now=3000+40*step;CHECK(fc_poll(&g,now,request)==8&&request[4]==2);count=request[6];axis=step/4;
  reply[0]=255;reply[1]=245;reply[2]=(uint8_t)(axis+1);reply[3]=(uint8_t)(count+2);reply[4]=0;
  if(step%4<2)reply[5]=1;
  else if(step%4==2){value=axis?400:610;reply[5]=(uint8_t)(value>>8);reply[6]=(uint8_t)value;reply[7]=(uint8_t)(3550>>8);reply[8]=(uint8_t)(3550&255);}
  else {value=axis?2097:2216;reply[5]=(uint8_t)(value>>8);reply[6]=(uint8_t)value;}
  sum=0;for(i=2;i<count+5;i++)sum+=reply[i];reply[count+5]=(uint8_t)~sum;
  for(i=0;i<count+6;i++)fc_byte(&g,reply[i],now+1);
  CHECK(g.state!=FC_FAULT&&g.tx_moves==0&&g.home_moves==0&&!g.link.armed);
 }
 CHECK(g.preflight==8&&g.state==FC_READY&&g.link.raw[0]==2216&&g.link.raw[1]==2097);
 CHECK(fc_poll(&g,3301,request)==0&&g.tx_moves==0&&!g.startup_pose_pending);
 CHECK(free_saved_reference[2]==2088&&free_saved_reference[3]==1961);
 puts("STARTUP_BOOT_PASS eight original preflight responses; displaced raw retained; no automatic home/motor; refs2088/1961");return 0;
}
