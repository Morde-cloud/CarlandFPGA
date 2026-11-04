"""Focused recorded-pause43/16-byte RX FIFO regression. No board/network I/O."""
from pathlib import Path
import binascii
import collections
import hashlib
import importlib.util
import json

H = Path(__file__).resolve().parent
W = H.parents[3]
DRIVER = W/'output/drill-live-link-20261104/baseline_mtr4/fpga_link/uartlite.py'
spec = importlib.util.spec_from_file_location('recorded_uartlite', DRIVER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
frame = bytes.fromhex('d34c01802b000000000000000000000000020f001d08a207040068000000e88b')
assert len(frame) == 32 and int.from_bytes(frame[4:8], 'little') == 43
assert binascii.crc_hqx(frame[:30], 65535) == int.from_bytes(frame[30:], 'little')
compiled = json.loads((H/'build4-evidence/PACER_SCHEDULE.json').read_bytes())
assert compiled['gap_ms'] == 1 and len(compiled['schedule_ms']) == 32

class Clock:
    def __init__(self, initial): self.now = initial
    def __call__(self): return self.now
    def sleep(self, duration): self.now += duration

class Fifo:
    def __init__(self, clock, arrivals):
        self.clock, self.arrivals = clock, collections.deque(zip(arrivals, frame))
        self.rx = collections.deque()
        self.overrun = False
        self.peak = self.dropped = 0
    def read(self, address):
        while self.arrivals and self.arrivals[0][0] <= self.clock.now:
            _, byte = self.arrivals.popleft()
            if len(self.rx) == 16:
                self.overrun = True
                self.dropped += 1
            else:
                self.rx.append(byte)
                self.peak = max(self.peak, len(self.rx))
        if address == 8:
            status = 4 | bool(self.rx) | (2 if len(self.rx) == 16 else 0) | (32 if self.overrun else 0)
            self.overrun = False  # PG142 error latch clears on status read.
            return status
        assert address == 0 and self.rx
        return self.rx.popleft()
    def write(self, *args): raise AssertionError('No write/retry/reset allowed in RX model')

def receive(arrivals, blackout, expect_error):
    clock = Clock(blackout)
    fifo = Fifo(clock, arrivals)
    uart = module.UartLite(fifo, clock=clock, sleep=clock.sleep)
    try:
        reply = uart.read_frame(timeout=0.3)
    except module.UartError as exc:
        assert expect_error and '0x27' in str(exc)
        return {'error':str(exc),'peak':fifo.peak,'dropped':fifo.dropped,'time_ms':clock.now*1000}
    assert not expect_error and reply == frame and fifo.dropped == 0
    assert binascii.crc_hqx(reply[:30],65535) == int.from_bytes(reply[30:],'little')
    return {'reply_exact':True,'CRC':True,'peak':fifo.peak,'dropped':fifo.dropped,'time_ms':clock.now*1000}

old_times = [(i+1)*10/115200 for i in range(32)]
new_times = [tick/1000 for tick in compiled['schedule_ms']]
old = receive(old_times,0.013227440,True)
new = receive(new_times,0.013227440,False)
long_stall = receive(new_times,0.04,True)
print(json.dumps({'cases':3,'fixture':'actual A169 pause43 response, not invented STOP44 ACK',
 'driver_SHA256':hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
 'old_burst_13ms_blackout':old,'compiled_C_pacing_13ms_blackout':new,
 'longer_blackout_still_raises_error':long_stall,
 'model_not_physical_test':True,'hardware_actions':0},sort_keys=True))
