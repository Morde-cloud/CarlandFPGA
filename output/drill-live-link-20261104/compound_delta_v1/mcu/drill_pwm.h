#ifndef DRILL_PWM_H
#define DRILL_PWM_H
#include <stdint.h>
/* Fixed direction TB6612 PWMA only; no encoder, rpm estimator or PID. */
void drill_pwm_init_off(void);
void drill_pwm_stop(void);
int drill_pwm_set_permille(uint16_t duty_permille);
uint16_t drill_pwm_get_permille(void);
#endif
