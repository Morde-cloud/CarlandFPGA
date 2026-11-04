#ifndef UART_REPLY_PACER_H
#define UART_REPLY_PACER_H
#include <stdint.h>

/* A's UARTLite RX FIFO is only16 bytes. Spread the unchanged32-byte reply
 * across about32ms instead of a2.8ms burst. This gate never waits, catches up,
 * changes a frame, or delays BUS receive/PWM/watchdog servicing. */
#define UART_REPLY_BYTE_GAP_MS 1u
typedef struct {uint32_t last_tx_ms;} UartReplyPacer;
static inline int uart_reply_due(const UartReplyPacer *p,uint32_t now) {
    return (uint32_t)(now-p->last_tx_ms)>=UART_REPLY_BYTE_GAP_MS;
}
static inline void uart_reply_sent(UartReplyPacer *p,uint32_t now) {
    p->last_tx_ms=now;
}
#endif
