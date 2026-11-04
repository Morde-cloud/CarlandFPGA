#include "uart_reply_pacer.h"
#include <stdio.h>
#include <stdint.h>
static unsigned checks;
#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"failed line%d\n",__LINE__);return 1;}}while(0)
int main(void) {
    UartReplyPacer p={0},wrap={UINT32_MAX};
    unsigned now,sent=0;uint32_t schedule[32];
    /* Drain an actual32-byte reply while every logical loop also services
     * other work. A host pause must not cause a catch-up burst. */
    for(now=0;now<=100;now++) {
        if(sent<32 && uart_reply_due(&p,now)) {
            schedule[sent++]=now;uart_reply_sent(&p,now);
            CHECK(!uart_reply_due(&p,now));
        }
    }
    CHECK(sent==32 && schedule[31]==32);
    uart_reply_sent(&p,200);CHECK(uart_reply_due(&p,201));
    CHECK(uart_reply_due(&p,250));uart_reply_sent(&p,250);
    CHECK(!uart_reply_due(&p,250) && uart_reply_due(&p,251));
    CHECK(uart_reply_due(&wrap,0));uart_reply_sent(&wrap,0);
    CHECK(!uart_reply_due(&wrap,0) && uart_reply_due(&wrap,1));
    printf("{\"checks\":%u,\"gap_ms\":%u,\"schedule_ms\":[",checks,UART_REPLY_BYTE_GAP_MS);
    for(now=0;now<32;now++)printf("%s%u",now?",":"",(unsigned)schedule[now]);
    puts("]}");return 0;
}
