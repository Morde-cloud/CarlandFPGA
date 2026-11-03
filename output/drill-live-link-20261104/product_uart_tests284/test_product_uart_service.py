"""New service mechanism checks. Synthetic Root/MMIO/HWH; no device opens."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

D = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(D))
import product_uart_service as service
from pc.codec import crc16_ccitt_false


def hwh(base=0x43c20000, size=4096, clock=50000000, baud=115200):
    return (f'<SYSTEM><MODULES><MODULE FULLNAME="/mcu_uart" INSTANCE="mcu_uart" VLNV="{service.UART_VLNV}">'
      '<BUSINTERFACES><BUSINTERFACE><PARAMETERS><PARAMETER NAME="FREQ_HZ" VALUE="50000000"/></PARAMETERS></BUSINTERFACE></BUSINTERFACES>'
      f'<PARAMETERS><PARAMETER NAME="C_S_AXI_ACLK_FREQ_HZ" VALUE="{clock}"/><PARAMETER NAME="C_BAUDRATE" VALUE="{baud}"/>'
      '<PARAMETER NAME="C_DATA_BITS" VALUE="8"/><PARAMETER NAME="C_USE_PARITY" VALUE="0"/></PARAMETERS>'
      f'<PORTS><PORT NAME="s_axi_aclk" CLKFREQUENCY="{clock}" SIGNAME="product_clk"/><PORT NAME="s_axi_aresetn" POLARITY="ACTIVE_LOW" SIGNAME="product_reset"/></PORTS>'
      f'</MODULE></MODULES><MEMRANGE INSTANCE="mcu_uart" SLAVEBUSINTERFACE="S_AXI" BASEVALUE="{hex(base)}" HIGHVALUE="{hex(base+size-1)}"/></SYSTEM>').encode()


class Clock:
    def __init__(self): self.now = 1.
    def __call__(self): return self.now
    def sleep(self, value): self.now += value


class FakeMMIO:
    def __init__(self):
        self.rx = bytearray(); self.tx = bytearray(); self.frames = []; self.writes = []
        self.armed = False; self.duty = 0; self.source = 0
        self.drop_next = None; self.result = 0; self.feedback = True; self.initial_status = None
        self.bad_stop = None
    def read(self, offset):
        if offset == 8:
            return self.initial_status if self.initial_status is not None else 4 | bool(self.rx)
        if offset == 0:
            return self.rx.pop(0)
        raise AssertionError('unexpected MMIO read')
    def write(self, offset, value):
        self.writes.append((offset, value))
        if offset != 4: raise AssertionError('reset/control write forbidden')
        self.tx.append(value)
        if len(self.tx) != 32: return
        frame = bytes(self.tx); self.tx.clear(); self.frames.append(frame)
        assert crc16_ccitt_false(frame[:30]) == int.from_bytes(frame[30:], 'little')
        op = frame[3]
        if op == 3: self.armed = False; self.duty = 0
        elif op == 1: self.armed = True; self.source = frame[8]
        elif op == 5: self.duty = struct.unpack_from('<H', frame, 14)[0]
        if self.drop_next == op:
            self.drop_next = None
            return
        reply = bytearray(32); reply[:4] = b'\xd3\x4c\x01\x80'; reply[4:8] = frame[4:8]
        reply[8] = self.armed; reply[9] = self.result
        if op == 2: reply[10:14] = frame[10:14]
        struct.pack_into('<H', reply, 14, self.duty); reply[17] = self.source
        if op == 3 and self.bad_stop == 'armed':reply[8]=1
        if op == 3 and self.bad_stop == 'duty':struct.pack_into('<H',reply,14,250)
        reply[18] = 0x0f if self.feedback else 0x0c; reply[19] = 0 if self.feedback else 255
        struct.pack_into('<HHHH', reply, 20, *( (2088,1961,0,0) if self.feedback else (65535,65535,65535,65535)))
        struct.pack_into('<H', reply, 30, crc16_ccitt_false(reply[:30])); self.rx.extend(reply)


class FakeRoot(service.RootLoadedProduct):
    simulation = True
    def __init__(self, blob=None):
        self.blob = hwh() if blob is None else blob; self.mmio = FakeMMIO(); self.opens = 0
        self.allowed = True; self.motor_allowed = False
        self.binding = service.ProductBinding('op284', '1'*64, 'boot284', 'build284', '2'*64,
            hashlib.sha256(self.blob).hexdigest(), '3'*64, 50000000,
            service.IpDescriptor('g05', 'custom:g05:2', 0x43c00000, 4096),
            service.IpDescriptor('trace', 'custom:trace:4', 0x43c10000, 4096),
            'product_clk', 'product_reset',
            service.UartDescriptor('mcu_uart', service.UART_VLNV, 0x43c20000, 4096,
                50000000,115200,8,False,1,'product_clk','product_reset'))
        self.current = self.binding
    def read_current(self): return self.current
    def read_hwh_bytes(self): return self.blob
    def authorize_transfer(self, profile, transfer):
        if not self.allowed: raise service.ServiceError('no actual B/operator grant')
    def authorize_motor(self, profile, transfer):
        if not self.motor_allowed: raise service.ServiceError('no separate motor grant')
    def open_uart_mmio(self, binding):
        assert binding == self.current; self.opens += 1; return self.mmio


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.path = Path(self.temp.name).resolve(); self.clock = Clock()
    def tearDown(self): self.temp.cleanup()
    def attach(self, root=None, transfer=None, profile=None, state=None):
        root = root or FakeRoot()
        transfer = transfer or service.BTransfer('op284','b-transfer284','observed-ready284',0,'4'*64,'MOTION_READY')
        profile = profile or service.Profile(root.binding, 'world284', 'MANUAL')
        return service.ProductUartService.attach(root, profile, transfer, state or self.path,
                                                clock=self.clock, sleep=self.clock.sleep)

    def test_import_and_JSON_cannot_grant_capability(self):
        self.assertNotIn('pynq', sys.modules)
        self.assertNotIn('serial', sys.modules)
        with self.assertRaises(service.ServiceError):
            self.attach(root={'authorized': True},profile=service.Profile(FakeRoot().binding,'world284','MANUAL'))

    def test_foreign_preloaded_protocol_module_rejected_before_MMIO(self):
        root=FakeRoot();module=sys.modules['pc.codec'];original=module.__file__
        try:
            module.__file__=str(self.path/'unrelated_codec.py')
            with self.assertRaisesRegex(service.ServiceError,'foreign imported'):self.attach(root)
        finally:module.__file__=original
        self.assertEqual(root.opens,0)

    def test_dynamic4KiB_open_is_STOP_STATUS_only_and_motor_disabled(self):
        root=FakeRoot(); s=self.attach(root)
        self.assertEqual([f[3] for f in root.mmio.frames], [3,4])
        self.assertEqual(root.opens,1); self.assertFalse(s._session.allow_motor)
        self.assertEqual(s.connection['event'],'uart_connected'); self.assertTrue(s.mcu_feedback_ready)
        self.assertFalse(any(offset==12 for offset,_ in root.mmio.writes))
        s.close()

    def test_overlap_type_clock_baud_and_reset_rejected_before_MMIO(self):
        for field,value in [('phys_addr',0x43c00000),('vlnv','xilinx.com:ip:axi_uartlite:1.0'),('clock_hz',100000000),('baud',1000000),('reset_net','other')]:
            root=FakeRoot(); bad=replace(root.binding,uart=replace(root.binding.uart,**{field:value}));root.current=bad
            with self.subTest(field=field), self.assertRaises(service.ServiceError): self.attach(root,profile=service.Profile(bad,'world284','MANUAL'),state=self.path/field)
            self.assertEqual(root.opens,0)

    def test_actual_BOOT_build_operation_mapping_and_FCLK_mismatch_rejected(self):
        for field,value in [('boot_id','other'),('build_id','other'),('operation_id','other'),('mapping_sha256','f'*64),('fclk_hz',100000000)]:
            root=FakeRoot();root.current=replace(root.current,**{field:value})
            with self.subTest(field=field),self.assertRaises(service.ServiceError): self.attach(root,state=self.path/field)
            self.assertEqual(root.opens,0)

    def test_HWH_hash_config_and_range_must_match_actual_descriptor(self):
        for kind,blob in [('bytes',hwh()+b' '),('clock',hwh(clock=100000000)),('baud',hwh(baud=1000000)),('range',hwh(base=0x43c30000))]:
            root=FakeRoot()
            root.blob=blob
            if kind!='bytes': root.binding=replace(root.binding,hwh_sha256=hashlib.sha256(blob).hexdigest());root.current=root.binding
            with self.subTest(kind=kind),self.assertRaises(service.ServiceError): self.attach(root,state=self.path/kind)
            self.assertEqual(root.opens,0)

    def test_real_Root_authorization_is_required(self):
        root=FakeRoot();root.allowed=False
        with self.assertRaisesRegex(service.ServiceError,'no actual'): self.attach(root)
        self.assertEqual(root.opens,0);self.assertEqual(root.mmio.frames,[])

    def test_stable_owner_lock_blocks_different_operation(self):
        root=FakeRoot();s=self.attach(root)
        other=FakeRoot();other.binding=replace(other.binding,operation_id='other');other.current=other.binding
        transfer=service.BTransfer('other','different','ready',0,'5'*64,'MOTION_READY')
        with self.assertRaises(service.ServiceError):self.attach(other,transfer=transfer)
        self.assertEqual(other.opens,0);s.close()

    def test_consumed_B_evidence_cannot_be_reused_under_new_operation(self):
        root=FakeRoot();s=self.attach(root);s.close()
        other=FakeRoot();other.binding=replace(other.binding,operation_id='other');other.current=other.binding
        transfer=service.BTransfer('other','newlabel','ready',0,'4'*64,'MOTION_READY')
        with self.assertRaises(FileExistsError): self.attach(other,transfer=transfer)
        self.assertEqual(other.opens,0)

    def test_unknown_FIFO_is_preserved_without_auto_reset(self):
        root=FakeRoot();root.mmio.initial_status=5
        with self.assertRaises(service.ServiceError): self.attach(root)
        self.assertEqual(root.mmio.frames,[]);self.assertEqual(root.mmio.writes,[])

    def test_diagnostic_only_connects_without_actuator_READY(self):
        root=FakeRoot();root.mmio.result=3;root.mmio.feedback=False
        transfer=service.BTransfer('op284','diag','fault-observation',0,'6'*64,'DIAGNOSTIC_ONLY')
        s=self.attach(root,transfer=transfer)
        self.assertFalse(s.connection['mcu_feedback_ready_observed']);self.assertFalse(s.connection['actuator_READY_authorized'])
        before=len(root.mmio.frames)
        for call in [lambda:s.pose(1,1),lambda:s.motor(1),s.enable_motor,lambda:s.make_follower([0,0,0,1]),s.keepalive]:
            with self.assertRaises(service.ServiceError):call()
        self.assertEqual(len(root.mmio.frames),before)
        self.assertEqual(s.status()['status']['result_code'],3)
        s.close();self.assertTrue(all(f[3] in (3,4) for f in root.mmio.frames))

    def test_motion_transfer_rejects_missing_feedback(self):
        root=FakeRoot();root.mmio.feedback=False
        with self.assertRaises(service.ServiceError):self.attach(root)
        self.assertFalse(any(f[3] in (1,2,5) for f in root.mmio.frames))

    def test_separate_motor_authorization_and_existing_follower(self):
        root=FakeRoot();s=self.attach(root)
        with self.assertRaises(service.ServiceError):s.enable_motor()
        self.assertEqual([f[3] for f in root.mmio.frames],[3,4])
        root.motor_allowed=True;s.enable_motor()
        follower=s.make_follower([0,0,0,1],motor_enabled=True)
        self.assertIs(follower.client,s);self.assertTrue(follower.motor_enabled)
        s.motor(10);self.assertEqual(root.mmio.frames[-1][3],5);s.motor(0)
        self.assertFalse(s._session.terminal) # ordinary OFF is not permanent terminal.
        s.close()

    def test_unknown_io_has_one_distinct_terminal_STOP_even_with_cleanup(self):
        for opcode in (4,5):
            root=FakeRoot();s=self.attach(root,state=self.path/str(opcode))
            if opcode==5:root.motor_allowed=True;s.enable_motor()
            root.mmio.drop_next=opcode
            with self.subTest(opcode=opcode),self.assertRaises(Exception):
                s.status() if opcode==4 else s.motor(10)
            s.stop('repeat');s.close()
            self.assertEqual(sum(f[3]==3 for f in root.mmio.frames),2) # initial + one terminal.
            self.assertTrue(s._session.stop_attempted)

    def test_invalid_archival_sample_reuses_STOP_and_initial_STOP_not_cached(self):
        root=FakeRoot();s=self.attach(root);f=s.make_follower([0,0,0,1])
        with self.assertRaises(Exception):f.push({'schema':'archival','live':False})
        f.stop();s.close()
        self.assertEqual(sum(frame[3]==3 for frame in root.mmio.frames),2)

    def test_changed_product_latches_and_never_safety_writes_old_address(self):
        root=FakeRoot();s=self.attach(root);before=len(root.mmio.frames)
        root.current=replace(root.binding,boot_id='new-boot')
        with self.assertRaises(service.ServiceError):s.status()
        root.current=root.binding
        with self.assertRaises(service.ServiceError):s.status()
        with self.assertRaises(service.ServiceError):s.close()
        self.assertEqual(len(root.mmio.frames),before)

    def test_STOP_requires_disarmed_OFF_truth_and_unknown_STOP_is_not_resent(self):
        for bad in ('armed','duty'):
            root=FakeRoot();root.mmio.bad_stop=bad
            with self.subTest(bad=bad),self.assertRaisesRegex(service.ServiceError,'not disarmed/OFF'):
                self.attach(root,state=self.path/bad)
            self.assertEqual([f[3] for f in root.mmio.frames],[3])
        root=FakeRoot();s=self.attach(root,state=self.path/'terminal')
        root.mmio.bad_stop='armed'
        with self.assertRaises(service.ServiceError):s.stop()
        with self.assertRaises(service.ServiceError):s.close()
        self.assertEqual(sum(f[3]==3 for f in root.mmio.frames),2)


if __name__=='__main__':unittest.main(verbosity=2)
