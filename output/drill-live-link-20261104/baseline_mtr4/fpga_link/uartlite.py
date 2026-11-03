"""Bounded polling of AXI UARTLite PG142 registers. Importing performs no I/O."""
from __future__ import annotations
import time


class UartError(RuntimeError):
    pass


class UartLite:
    RX, TX, STATUS, CONTROL = 0x0, 0x4, 0x8, 0xC
    RX_VALID, TX_FULL, ERRORS = 0x01, 0x08, 0xE0

    def __init__(self, mmio, *, clock=time.monotonic, sleep=time.sleep):
        self.mmio, self.clock, self.sleep = mmio, clock, sleep

    def reset_fifos(self):
        self.mmio.write(self.CONTROL, 3)  # TX/RX FIFO reset; IRQ disabled.

    def _status(self):
        status = self.mmio.read(self.STATUS)
        if status & self.ERRORS:
            raise UartError('UARTLite RX overrun/frame/parity error: 0x%02x' % status)
        return status

    def write_frame(self, data, timeout=0.3):
        if len(data) != 32:
            raise ValueError('one 32-byte MCU frame required')
        deadline = self.clock() + timeout
        for octet in data:
            while self._status() & self.TX_FULL:
                if self.clock() >= deadline:
                    raise UartError('UARTLite TX timeout; no retry')
                self.sleep(0.0001)
            if self.clock() >= deadline:
                raise UartError('UARTLite TX deadline exceeded; partial frame not replayed')
            self.mmio.write(self.TX, octet)

    def read_frame(self, timeout=0.3):
        deadline = self.clock() + timeout
        data = bytearray()
        while self.clock() < deadline:
            if self._status() & self.RX_VALID:
                data.append(self.mmio.read(self.RX) & 255)
                # Startup noise may precede a frame. CRC validation is by caller.
                while data and data[0] != 0xD3:
                    del data[0]
                if len(data) > 1 and data[1] != 0x4C:
                    del data[0]
                    continue
                if len(data) == 32:
                    return bytes(data)
            else:
                self.sleep(0.0001)
        raise UartError('UARTLite RX timeout; partial reply discarded, no retry')
