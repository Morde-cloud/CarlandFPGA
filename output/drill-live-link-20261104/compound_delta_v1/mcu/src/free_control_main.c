/* MTR5 UART1 compound-delta controller; original pinout and finite leases. */
#include "ti_msp_dl_config.h"
#include "free_control.h"
#include "motor_control.h"
#include "drill_pwm.h"
#include "uart_reply_pacer.h"
#include <string.h>
static volatile uint32_t ticks;
void SysTick_Handler(void) {ticks++;}
FreeControl free_diagnostics;
MotorRuntime motor_diagnostics;
volatile uint32_t motor_pwm_applied,motor_pwm_peak,motor_gpio_output,motor_pincm;
typedef struct {uint8_t data[128],head,tail;} TxQueue;
static TxQueue pc_tx,bus_tx;
static UartReplyPacer pc_reply_pacer;
volatile uint32_t free_tx_overflows;
volatile uint32_t free_limit_request; /* SWD-only explicit commissioning mailbox */
static int send(TxQueue *q,const uint8_t *p,size_t n) {
    size_t i;unsigned used=(q->head-q->tail)&127u;
    if(n>127u-used) {free_tx_overflows++;return 0;}
    for(i=0;i<n;i++) {q->data[q->head]=p[i];q->head=(uint8_t)((q->head+1u)&127u);}
    return 1;
}
static void service_tx(UART_Regs *uart,TxQueue *q) {
    unsigned budget=32;
    while(budget-- && q->tail!=q->head && !DL_UART_Main_isTXFIFOFull(uart)) {
        DL_UART_Main_transmitData(uart,q->data[q->tail]);
        q->tail=(uint8_t)((q->tail+1u)&127u);
    }
}
static void service_pc_tx(uint32_t now) {
    if(pc_tx.tail==pc_tx.head || !uart_reply_due(&pc_reply_pacer,now) ||
       DL_UART_Main_isTXFIFOFull(PC_UART_INST))return;
    DL_UART_Main_transmitData(PC_UART_INST,pc_tx.data[pc_tx.tail]);
    pc_tx.tail=(uint8_t)((pc_tx.tail+1u)&127u);
    uart_reply_sent(&pc_reply_pacer,ticks);
}
int main(void) {
    uint8_t pc[32],used=0,reply[32],bus[18];uint32_t last_pc=0;unsigned budget;
    SYSCFG_DL_init();drill_pwm_init_off();mc_init(&motor_diagnostics);SysTick_Config(CPUCLK_FREQ/1000u);fc_init(&free_diagnostics,0);
    for(;;) {
        uint32_t now=ticks;size_t n;
        budget=64;
        while(budget-- && !DL_UART_Main_isRXFIFOEmpty(BUS_UART_INST))
            fc_byte(&free_diagnostics,DL_UART_Main_receiveData(BUS_UART_INST),ticks);
        now=ticks;if(used && (uint32_t)(now-last_pc)>50u) used=0;
        budget=64;
        while(budget-- && !DL_UART_Main_isRXFIFOEmpty(PC_UART_INST)) {
            uint8_t byte=DL_UART_Main_receiveData(PC_UART_INST);last_pc=ticks;
            if(!used && byte!=0xd3) continue;
            if(used==1 && byte!=0x4c) {used=byte==0xd3?1u:0u;continue;}
            pc[used++]=byte;
            if(used==32) {
                unsigned i;mc_command(&motor_diagnostics,&free_diagnostics,pc,ticks,reply);
                if(!send(&pc_tx,reply,32))mc_stop(&motor_diagnostics,&free_diagnostics,ticks);
                used=0;
                if(reply[9]==DEMO_CRC || reply[9]==DEMO_FORMAT)
                    for(i=1;i<31;i++) if(pc[i]==0xd3 && pc[i+1]==0x4c) {used=(uint8_t)(32-i);memmove(pc,pc+i,used);break;}
            }
        }
        if(!DL_GPIO_readPins(BUTTON_PORT,BUTTON_S2_PIN)) mc_stop(&motor_diagnostics,&free_diagnostics,ticks);
        if(free_limit_request==0x504c3930u && !free_diagnostics.pending) {
            free_limit_request=0;
            if(!fc_limit_begin(&free_diagnostics,ticks))free_diagnostics.limit_result=4;
        }
        n=fc_poll(&free_diagnostics,ticks,bus);
        if(n && !send(&bus_tx,bus,n))mc_stop(&motor_diagnostics,&free_diagnostics,ticks);
        /* Replies are paced without blocking. Continue draining both receive
         * FIFOs and servicing the existing motor lease on every iteration. */
        service_tx(BUS_UART_INST,&bus_tx);service_pc_tx(ticks);
        mc_tick(&motor_diagnostics,&free_diagnostics,ticks);
        if(motor_diagnostics.duty!=drill_pwm_get_permille())
            (void)drill_pwm_set_permille(motor_diagnostics.duty);
        motor_pwm_applied=drill_pwm_get_permille();
        if(motor_pwm_applied>motor_pwm_peak)motor_pwm_peak=motor_pwm_applied;
        motor_gpio_output=GPIO_DRILL_PWM_C0_PORT->DOUT31_0 & GPIO_DRILL_PWM_C0_PIN;
        motor_pincm=IOMUX->SECCFG.PINCM[GPIO_DRILL_PWM_C0_IOMUX];
        DL_GPIO_clearPins(STATUS_PORT,STATUS_BLUE_PIN|STATUS_RED_PIN|STATUS_GREEN_PIN);
        DL_GPIO_setPins(STATUS_PORT,free_diagnostics.state==FC_FAULT?STATUS_RED_PIN:
            free_diagnostics.state==FC_LINK_WAIT?(STATUS_RED_PIN|STATUS_GREEN_PIN):
            free_diagnostics.state==FC_READY?STATUS_GREEN_PIN:((ticks/200u)&1u)?STATUS_BLUE_PIN:0u);
    }
}
