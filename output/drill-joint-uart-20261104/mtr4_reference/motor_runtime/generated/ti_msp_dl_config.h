/*
 * Copyright (c) 2023, Texas Instruments Incorporated - http://www.ti.com
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * *  Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * *  Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * *  Neither the name of Texas Instruments Incorporated nor the names of
 *    its contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 * EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

/*
 *  ============ ti_msp_dl_config.h =============
 *  Configured MSPM0 DriverLib module declarations
 *
 *  DO NOT EDIT - This file is generated for the MSPM0G350X
 *  by the SysConfig tool.
 */
#ifndef ti_msp_dl_config_h
#define ti_msp_dl_config_h

#define CONFIG_MSPM0G350X
#define CONFIG_MSPM0G3507

#if defined(__ti_version__) || defined(__TI_COMPILER_VERSION__)
#define SYSCONFIG_WEAK __attribute__((weak))
#elif defined(__IAR_SYSTEMS_ICC__)
#define SYSCONFIG_WEAK __weak
#elif defined(__GNUC__)
#define SYSCONFIG_WEAK __attribute__((weak))
#endif

#include <ti/devices/msp/msp.h>
#include <ti/driverlib/driverlib.h>
#include <ti/driverlib/m0p/dl_core.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 *  ======== SYSCFG_DL_init ========
 *  Perform all required MSP DL initialization
 *
 *  This function should be called once at a point before any use of
 *  MSP DL.
 */


/* clang-format off */

#define POWER_STARTUP_DELAY                                                (16)



#define CPUCLK_FREQ                                                     32000000



/* Defines for DRILL_PWM */
#define DRILL_PWM_INST                                                     TIMG0
#define DRILL_PWM_INST_IRQHandler                               TIMG0_IRQHandler
#define DRILL_PWM_INST_INT_IRQN                                 (TIMG0_INT_IRQn)
#define DRILL_PWM_INST_CLK_FREQ                                         32000000
/* GPIO defines for channel 0 */
#define GPIO_DRILL_PWM_C0_PORT                                             GPIOA
#define GPIO_DRILL_PWM_C0_PIN                                     DL_GPIO_PIN_12
#define GPIO_DRILL_PWM_C0_IOMUX                                  (IOMUX_PINCM34)
#define GPIO_DRILL_PWM_C0_IOMUX_FUNC                 IOMUX_PINCM34_PF_TIMG0_CCP0
#define GPIO_DRILL_PWM_C0_IDX                                DL_TIMER_CC_0_INDEX



/* Defines for PC_UART */
#define PC_UART_INST                                                       UART1
#define PC_UART_INST_FREQUENCY                                          32000000
#define PC_UART_INST_IRQHandler                                 UART1_IRQHandler
#define PC_UART_INST_INT_IRQN                                     UART1_INT_IRQn
#define GPIO_PC_UART_RX_PORT                                               GPIOB
#define GPIO_PC_UART_TX_PORT                                               GPIOB
#define GPIO_PC_UART_RX_PIN                                        DL_GPIO_PIN_7
#define GPIO_PC_UART_TX_PIN                                        DL_GPIO_PIN_6
#define GPIO_PC_UART_IOMUX_RX                                    (IOMUX_PINCM24)
#define GPIO_PC_UART_IOMUX_TX                                    (IOMUX_PINCM23)
#define GPIO_PC_UART_IOMUX_RX_FUNC                     IOMUX_PINCM24_PF_UART1_RX
#define GPIO_PC_UART_IOMUX_TX_FUNC                     IOMUX_PINCM23_PF_UART1_TX
#define PC_UART_BAUD_RATE                                               (115200)
#define PC_UART_IBRD_32_MHZ_115200_BAUD                                     (17)
#define PC_UART_FBRD_32_MHZ_115200_BAUD                                     (23)
/* Defines for BUS_UART */
#define BUS_UART_INST                                                      UART0
#define BUS_UART_INST_FREQUENCY                                         32000000
#define BUS_UART_INST_IRQHandler                                UART0_IRQHandler
#define BUS_UART_INST_INT_IRQN                                    UART0_INT_IRQn
#define GPIO_BUS_UART_RX_PORT                                              GPIOA
#define GPIO_BUS_UART_TX_PORT                                              GPIOA
#define GPIO_BUS_UART_RX_PIN                                       DL_GPIO_PIN_1
#define GPIO_BUS_UART_TX_PIN                                       DL_GPIO_PIN_0
#define GPIO_BUS_UART_IOMUX_RX                                    (IOMUX_PINCM2)
#define GPIO_BUS_UART_IOMUX_TX                                    (IOMUX_PINCM1)
#define GPIO_BUS_UART_IOMUX_RX_FUNC                     IOMUX_PINCM2_PF_UART0_RX
#define GPIO_BUS_UART_IOMUX_TX_FUNC                     IOMUX_PINCM1_PF_UART0_TX
#define BUS_UART_BAUD_RATE                                              (115200)
#define BUS_UART_IBRD_32_MHZ_115200_BAUD                                    (17)
#define BUS_UART_FBRD_32_MHZ_115200_BAUD                                    (23)





/* Port definition for Pin Group BUTTON */
#define BUTTON_PORT                                                      (GPIOB)

/* Defines for S2: GPIOB.21 with pinCMx 49 on package pin 20 */
#define BUTTON_S2_PIN                                           (DL_GPIO_PIN_21)
#define BUTTON_S2_IOMUX                                          (IOMUX_PINCM49)
/* Port definition for Pin Group STATUS */
#define STATUS_PORT                                                      (GPIOB)

/* Defines for BLUE: GPIOB.22 with pinCMx 50 on package pin 21 */
#define STATUS_BLUE_PIN                                         (DL_GPIO_PIN_22)
#define STATUS_BLUE_IOMUX                                        (IOMUX_PINCM50)
/* Defines for RED: GPIOB.26 with pinCMx 57 on package pin 28 */
#define STATUS_RED_PIN                                          (DL_GPIO_PIN_26)
#define STATUS_RED_IOMUX                                         (IOMUX_PINCM57)
/* Defines for GREEN: GPIOB.27 with pinCMx 58 on package pin 29 */
#define STATUS_GREEN_PIN                                        (DL_GPIO_PIN_27)
#define STATUS_GREEN_IOMUX                                       (IOMUX_PINCM58)


/* clang-format on */

void SYSCFG_DL_init(void);
void SYSCFG_DL_initPower(void);
void SYSCFG_DL_GPIO_init(void);
void SYSCFG_DL_SYSCTL_init(void);
void SYSCFG_DL_DRILL_PWM_init(void);
void SYSCFG_DL_PC_UART_init(void);
void SYSCFG_DL_BUS_UART_init(void);


bool SYSCFG_DL_saveConfiguration(void);
bool SYSCFG_DL_restoreConfiguration(void);

#ifdef __cplusplus
}
#endif

#endif /* ti_msp_dl_config_h */
