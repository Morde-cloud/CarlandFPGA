#include "ti_msp_dl_config.h"
#include "drill_pwm.h"
#if DRILL_PWM_INST_CLK_FREQ != 32000000
#error Recheck PWM clock and 20kHz period before building
#endif
#define PERIOD_COUNTS 1600u
static uint16_t selected_duty;
static void gpio_level(int high) {
    if(high)DL_GPIO_setPins(GPIO_DRILL_PWM_C0_PORT,GPIO_DRILL_PWM_C0_PIN);
    else DL_GPIO_clearPins(GPIO_DRILL_PWM_C0_PORT,GPIO_DRILL_PWM_C0_PIN);
    DL_GPIO_initDigitalOutput(GPIO_DRILL_PWM_C0_IOMUX);
    DL_GPIO_enableOutput(GPIO_DRILL_PWM_C0_PORT,GPIO_DRILL_PWM_C0_PIN);
}
void drill_pwm_stop(void) {
    /* Force the pin LOW independently of timer endpoint/polarity behavior. */
    gpio_level(0);DL_TimerG_stopCounter(DRILL_PWM_INST);selected_duty=0;
}
void drill_pwm_init_off(void) {drill_pwm_stop();}
uint16_t drill_pwm_get_permille(void) {return selected_duty;}
int drill_pwm_set_permille(uint16_t duty) {
    uint32_t compare;
    if(duty>1000u){drill_pwm_stop();return 0;}
    if(duty==selected_duty && duty!=0u)return 1; /* Same duty renewal must not restart the timer. */
    if(!duty){drill_pwm_stop();return 1;}
    if(duty==1000u){DL_TimerG_stopCounter(DRILL_PWM_INST);gpio_level(1);selected_duty=duty;return 1;}
    /* Generated edge-aligned down-counter: HIGH on LOAD, LOW on compare. */
    compare=(PERIOD_COUNTS-1u)-((PERIOD_COUNTS*(uint32_t)duty)/1000u); /* DOWN: high=(LOAD-CC)/(LOAD+1). */
    DL_TimerG_stopCounter(DRILL_PWM_INST);
    DL_TimerG_setCaptureCompareValue(DRILL_PWM_INST,compare,DL_TIMER_CC_0_INDEX);
    DL_TimerG_setTimerCount(DRILL_PWM_INST,PERIOD_COUNTS-1u);
    DL_GPIO_initPeripheralOutputFunction(GPIO_DRILL_PWM_C0_IOMUX,GPIO_DRILL_PWM_C0_IOMUX_FUNC);
    DL_TimerG_startCounter(DRILL_PWM_INST);selected_duty=duty;return 1;
}
