"""Focused startup seam checks with real service/codec and synthetic UART only.

Run in the delivered layout (baseline_mtr4/ alongside this file). No serial,
PYNQ, SSH or actuator is opened. UART acknowledgments below are test models.
"""
from dataclasses import replace
import hashlib
import struct
import tempfile
from pathlib import Path
import threading
import unittest

import product_uart_service as service
from product_uart_stdio import ExistingStreamSession
from delta_codec import encode_startup_prepare, crc16_ccitt_false, speed_to_pwm


class Clock:
    def __init__(self): self.now = 1.
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


class MMIO:
    def __init__(self):
        self.rx = bytearray(); self.tx = bytearray(); self.frames = []
        self.armed = False; self.duty = self.source = self.speed = 0
        self.yaw = 950; self.pitch = 949
        self.drop = None; self.bad_prepare = None; self.prepared = None
        self.prepare_reply = None
    def read(self, offset):
        if offset == 8: return 4 | bool(self.rx)
        if offset == 0: return self.rx.pop(0)
        raise AssertionError('unexpected register read')
    def write(self, offset, value):
        assert offset == 4, 'no reset/control writes'
        self.tx.append(value)
        if len(self.tx) != 32: return
        f = bytes(self.tx); self.tx.clear(); self.frames.append(f)
        assert crc16_ccitt_false(f[:30]) == int.from_bytes(f[30:], 'little')
        op = f[3]
        if op == 3: self.armed = False; self.duty = self.speed = 0; self.prepared = None
        elif op == 1: self.armed = True; self.source = f[8]
        elif op == 8:
            assert not self.armed and not self.duty
            self.prepared = (int.from_bytes(f[24:28], 'little'), int.from_bytes(f[14:16], 'little'))
            self.yaw = self.pitch = 0; self.source = f[8]
        elif op == 6:
            assert self.armed
            y,p,s = struct.unpack_from('<hhh', f, 10)
            self.yaw += y; self.pitch += p; self.speed = max(0,min(1000,self.speed+s));self.duty = speed_to_pwm(self.speed)
            self.prepared = None
        if self.drop == op: self.drop = None; return
        r = bytearray(32); r[:4] = b'\xd3\x4c\x01\x80'; r[4:8] = f[4:8]
        r[8] = self.armed; r[17] = self.source; r[18] = 15
        struct.pack_into('<hhH', r, 10, self.yaw, self.pitch, self.duty)
        struct.pack_into('<HHHH', r, 20, 2216, 2097, 10, 20)
        if op == 8 and self.bad_prepare == 'source': r[17] = 1
        if op == 8 and self.bad_prepare == 'armed': r[8] = 1
        if op == 8 and self.bad_prepare == 'nonzero': struct.pack_into('<h', r, 10, 1)
        struct.pack_into('<H', r, 30, crc16_ccitt_false(r[:30]))
        if op == 8: self.prepare_reply = bytes(r)
        self.rx.extend(r)


class Root(service.RootLoadedProduct):
    simulation = True
    def __init__(self):
        self.mmio = MMIO(); self.motor_allowed = False; self.opens = 0
        self.blob = (f'<SYSTEM><MODULES><MODULE FULLNAME="/mcu_uart" INSTANCE="mcu_uart" VLNV="{service.UART_VLNV}">'
          '<BUSINTERFACES><BUSINTERFACE><PARAMETERS><PARAMETER NAME="FREQ_HZ" VALUE="50000000"/></PARAMETERS></BUSINTERFACE></BUSINTERFACES>'
          '<PARAMETERS><PARAMETER NAME="C_S_AXI_ACLK_FREQ_HZ" VALUE="50000000"/><PARAMETER NAME="C_BAUDRATE" VALUE="115200"/>'
          '<PARAMETER NAME="C_DATA_BITS" VALUE="8"/><PARAMETER NAME="C_USE_PARITY" VALUE="0"/></PARAMETERS>'
          '<PORTS><PORT NAME="s_axi_aclk" CLKFREQUENCY="50000000" SIGNAME="product_clk"/><PORT NAME="s_axi_aresetn" POLARITY="ACTIVE_LOW" SIGNAME="product_reset"/></PORTS>'
          '</MODULE></MODULES><MEMRANGE INSTANCE="mcu_uart" SLAVEBUSINTERFACE="S_AXI" BASEVALUE="0x43c20000" HIGHVALUE="0x43c20fff"/></SYSTEM>').encode()
        self.binding = service.ProductBinding('startup503', '1'*64, 'boot503', 'build503', '2'*64,
            hashlib.sha256(self.blob).hexdigest(), '3'*64, 50000000,
            service.IpDescriptor('g05','custom:g05:2',0x43c00000,4096),
            service.IpDescriptor('trace','custom:trace:4',0x43c10000,4096),
            'product_clk','product_reset',service.UartDescriptor('mcu_uart',service.UART_VLNV,
                0x43c20000,4096,50000000,115200,8,False,1,'product_clk','product_reset'))
        self.current = self.binding
    def read_current(self): return self.current
    def read_hwh_bytes(self): return self.blob
    def authorize_transfer(self, profile, transfer): return None
    def authorize_motor(self, profile, transfer):
        if not self.motor_allowed: raise service.ServiceError('separate motor grant absent')
    def open_uart_mmio(self, binding): self.opens += 1; return self.mmio


class StartupChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.path = Path(self.temp.name).resolve()
        self.clock = Clock(); self.root = Root(); self.sessions = []
    def tearDown(self):
        for s in self.sessions:
            try:s.close()
            except Exception:pass
        self.temp.cleanup()
    def attach(self, scope='MOTION_READY'):
        grant = service.BTransfer('startup503','transfer503','observed503',301,'4'*64,scope)
        s = service.ProductUartService.attach(self.root,service.Profile(self.root.binding,'world503','FPGA_OUTPUT'),
            grant,self.path,clock=self.clock,sleep=self.clock.sleep)
        self.sessions.append(s); return s

    def test_vector_exact_crc_and_strict_integer_validation(self):
        f=encode_startup_prepare(302,'FPGA_OUTPUT',1793772501,880,500)
        self.assertEqual(f.hex(),'d34c01082e01000002010000000070030000f40100000000d5cbea6a00008d5b')
        for kwargs in [dict(seq=True),dict(run_id=0),dict(initial_speed_permille=1001),dict(move_ms=99),dict(source='WRONG')]:
            args=dict(seq=302,source='FPGA_OUTPUT',run_id=1793772501,initial_speed_permille=880,move_ms=500);args.update(kwargs)
            with self.assertRaises(ValueError):encode_startup_prepare(**args)

    def test_prepare_rpc_returns_real_model_ACK_off_and_independent_preset(self):
        s=self.attach(); before=len(self.root.mmio.frames)
        r=s.startup_prepare(1793772501,880)
        self.assertEqual([f[3] for f in self.root.mmio.frames[before:]],[8])
        self.assertEqual(r['prepared_run_id'],1793772501);self.assertEqual(r['prepared_speed_permille'],880)
        self.assertEqual(r['uart_ack_hex'],self.root.mmio.prepare_reply.hex())
        self.assertTrue(r['motor_off']);self.assertFalse(r['status']['armed'])
        self.assertFalse(s._session.allow_motor);self.assertEqual(s._session.delta_speed_norm,0)
        self.assertEqual(r['status']['yaw_feedback']['raw_position'],2216) # No forged home arrival.
        self.assertTrue(r['uart_ack_is_not_arrival']);self.assertIsNone(s._session.delta_source_deadline_ms)
        self.assertEqual(self.root.mmio.prepared,(1793772501,880))

    def test_first_real_delta_starts_from_zero_and_resume_never_rehomes(self):
        s=self.attach();s.startup_prepare(1793772501,880)
        self.clock.now += 1.0 # Caller owns wait, not service.
        self.root.motor_allowed=True;s.enable_motor()
        r=s.delta(1,1793772501,100,-200,880,source_valid_for_ms=1000)
        self.assertEqual(r['commanded_speed_permille'],880);self.assertEqual(r['commanded_pwm_permille'],690)
        self.assertEqual([f[3] for f in self.root.mmio.frames],[3,4,8,4,1,6])
        self.assertFalse(s._session.prepared_active)
        s.delta(2,1793772501,0,0,0,source_valid_for_ms=1000)
        self.assertEqual(sum(f[3]==8 for f in self.root.mmio.frames),1)

    def test_duplicate_or_stale_prepare_is_never_resent(self):
        s=self.attach();s.startup_prepare(1793772501,880)
        with self.assertRaisesRegex(Exception,'already prepared'):s.startup_prepare(1793772501,880)
        self.assertEqual(sum(f[3]==8 for f in self.root.mmio.frames),1)
        self.assertFalse(s._session.prepared_active)
        self.assertEqual(s._session.prepared_run_id,1793772501)

    def test_unknown_prepare_stops_once_no_replay_through_cleanup(self):
        s=self.attach();self.root.mmio.drop=8
        with self.assertRaisesRegex(Exception,'timeout|missing'):s.startup_prepare(1793772501,880)
        s.close()
        self.assertEqual([f[3] for f in self.root.mmio.frames],[3,4,8,3])
        self.assertTrue(s._session.failed)

    def test_invalid_intent_has_no_prepare_ARM_or_motor(self):
        s=self.attach()
        with self.assertRaises(Exception):s.startup_prepare(1793772501,True)
        self.assertEqual([f[3] for f in self.root.mmio.frames],[3,4,3])

    def test_existing_stream_preserves_request_envelope_and_STOP_cancels(self):
        s=self.attach();stream=ExistingStreamSession(s);session=s._session
        req=dict(op='startup_prepare',session=session.session_id,request_id=19,
            expires_ms=session.clock_ms()+500,run_id=1793772501,initial_speed_permille=880,move_ms=500)
        r=stream.dispatch(req);self.assertEqual(r['request_id'],19)
        stream.dispatch(dict(op='stop',session=session.session_id,request_id=20,expires_ms=0))
        self.assertFalse(session.prepared_active);self.assertIsNone(self.root.mmio.prepared)

    def test_diagnostic_and_changed_identity_cannot_prepare(self):
        s=self.attach(scope='DIAGNOSTIC_ONLY');before=len(self.root.mmio.frames)
        with self.assertRaises(service.ServiceError):s.startup_prepare(1793772501,880)
        self.assertEqual(len(self.root.mmio.frames),before)
        self.root.current=replace(self.root.binding,boot_id='new-boot')
        with self.assertRaises(service.ServiceError):s.startup_prepare(1793772501,880)
        self.assertEqual(len(self.root.mmio.frames),before)

    def test_wrong_thread_rejected_before_IO(self):
        s=self.attach();errors=[];before=len(self.root.mmio.frames)
        def other():
            try:s.startup_prepare(1793772501,880)
            except Exception as e:errors.append(e)
        t=threading.Thread(target=other);t.start();t.join()
        self.assertEqual(len(errors),1);self.assertEqual(len(self.root.mmio.frames),before)

    def test_mismatching_first_run_does_not_ARM_or_drive(self):
        s=self.attach();s.startup_prepare(1793772501,880)
        self.root.motor_allowed=True;s.enable_motor()
        with self.assertRaisesRegex(Exception,'match the prepared run'):
            s.delta(1,1793772502,0,0,880,source_valid_for_ms=1000)
        self.assertFalse(any(f[3] in (1,6) for f in self.root.mmio.frames))

    def test_prepare_ACK_source_and_zero_targets_are_checked(self):
        s=self.attach();self.root.mmio.bad_prepare='source'
        with self.assertRaisesRegex(Exception,'matching zero-target'):s.startup_prepare(1793772501,880)
        self.assertEqual(sum(f[3]==8 for f in self.root.mmio.frames),1)
        self.assertEqual([f[3] for f in self.root.mmio.frames][-1],3)

    def test_legacy_home_cannot_bypass_prepared_round(self):
        s=self.attach();s.startup_prepare(1793772501,880)
        with self.assertRaisesRegex(Exception,'legacy motion'):s.pose(0,0)
        self.assertFalse(any(f[3] in (1,2,5) for f in self.root.mmio.frames))


if __name__=='__main__': unittest.main(verbosity=2)
