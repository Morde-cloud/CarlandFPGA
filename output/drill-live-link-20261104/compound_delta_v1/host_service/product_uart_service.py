"""Already-loaded product UART service. Import has no hardware or port effects.

A's sole Root supplies the live capability below. Profile/transfer records are
constraints and audit labels, never independent authorization. No PYNQ import,
Overlay, bitstream download, clock change, reset or MCU boot inference exists.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET

from drill_live_link.session_client import SessionClient, SequenceJournal, VariableDisplaySession
from drill_live_link.compound_session import CompoundDeltaSession
from drill_live_link.model import FollowMapper, Limits
from drill_live_link.follower import Follower
from fpga_link.uartlite import UartLite

REQUIREMENTS_SHA256 = '2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d'
UART_VLNV = 'xilinx.com:ip:axi_uartlite:2.0'
PROTECTED = ((0x43C00000, 0x1000), (0x43C10000, 0x1000))
DEPENDENCIES = {
    'delta_codec': ('delta_codec.py', '01f7beca397a41c23fe3562000a0386e8d2a03a462236b90060a392bb612c9ee'),
    'drill_live_link.compound_session': ('drill_live_link/compound_session.py', 'd53f10f708a7a8dc7339566838d8de35c0666962068b02f3358d3c0723e1e3ba'),
    'motor_runtime.variable_session': ('baseline_mtr4/motor_runtime/variable_session.py', '1d5ce3f2aea1849b7e55e164e6c8d1db9e5d333e8a821f1feac9e3416f4d1d38'),
    'fpga_link.session': ('baseline_mtr4/fpga_link/session.py', '5e7765a01e49b1b7c324d338773b7689f140c8fe6dd09f044d27cd62438a39ba'),
    'fpga_link.uartlite': ('baseline_mtr4/fpga_link/uartlite.py', '29cc8160790bdc2d6fa25be1de1994dc39586fba3d884b9826a2d2c030eed778'),
    'pc.codec': ('baseline_mtr4/pc/codec.py', '62cf254d4d4b519578da364b49f0555d61de386ee1430e664e63013fadbed006'),
    'drill_live_link.session_client': ('drill_live_link/session_client.py', '6d3332f9f671949cd6e909807b00bc7b454b9caaa99c3486fdd738a0e094d145'),
    'drill_live_link.follower': ('drill_live_link/follower.py', '6b975c4cb3ad23723b131ee088edfaa9810fa387af0be61382497ffe088a1134'),
    'drill_live_link.model': ('drill_live_link/model.py', '249d0e6c253de8f91402ba5e35f0d385eea789a886c14ea249ad092bf5a69333'),
}


class ServiceError(RuntimeError):
    pass


def _need(ok, reason):
    if not ok:
        raise ServiceError(reason)


def _text(value):
    _need(type(value) is str and 0 < len(value) <= 256 and value.isascii(), 'bounded ASCII identity')
    return value


def _hex(value):
    _need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'SHA256 identity')
    return value


def _uint(value, maximum=(1 << 64)-1):
    _need(type(value) is int and 0 <= value <= maximum, 'unsigned integer')
    return value


def _raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def _verify_dependencies():
    directory = Path(__file__).resolve().parent
    for name, (relative, expected) in DEPENDENCIES.items():
        module = sys.modules.get(name)
        wanted = (directory/relative).resolve()
        _need(module is not None and Path(module.__file__).resolve() == wanted,
              'stale or foreign imported dependency: '+name)
        _need(hashlib.sha256(wanted.read_bytes()).hexdigest() == expected, 'dependency bytes changed: '+name)


@dataclass(frozen=True)
class IpDescriptor:
    name: str
    vlnv: str
    phys_addr: int
    addr_range: int

    def validate(self):
        _text(self.name); _text(self.vlnv)
        _uint(self.phys_addr, 0xffffffff); _uint(self.addr_range, 0x100000000)
        _need(self.phys_addr % 4 == 0 and self.addr_range >= 16
              and self.phys_addr+self.addr_range <= 0x100000000, 'IP address range')


@dataclass(frozen=True)
class UartDescriptor(IpDescriptor):
    clock_hz: int
    baud: int
    data_bits: int
    parity: bool
    stop_bits: int
    clock_net: str
    reset_net: str

    @property
    def fullname(self):
        return '/'+self.name.strip('/')

    @property
    def base(self):
        return self.phys_addr

    @property
    def size(self):
        return self.addr_range

    def validate(self):
        super().validate()
        _need(self.fullname.strip('/') == 'mcu_uart', 'independent mcu_uart only')
        _text(self.clock_net); _text(self.reset_net)
        _uint(self.base, 0xffffffff); _uint(self.size, 0x100000000)
        _need(self.base % 4 == 0 and self.size >= 16 and self.base+self.size <= 0x100000000, 'UART address range')
        _need(self.vlnv == UART_VLNV and type(self.clock_hz) is int and self.clock_hz == 50_000_000,
              'UART type/50MHz mismatch')
        _need(type(self.baud) is int and self.baud == 115200 and type(self.data_bits) is int and self.data_bits == 8
              and type(self.parity) is bool and self.parity is False and type(self.stop_bits) is int and self.stop_bits == 1,
              'UART 115200 8N1 mismatch')
        _need(all(self.base+self.size <= base or base+size <= self.base for base, size in PROTECTED),
              'UART overlaps G05 or TRACE')


@dataclass(frozen=True)
class ProductBinding:
    operation_id: str
    request_hash: str
    boot_id: str
    build_id: str
    bit_sha256: str
    hwh_sha256: str
    mapping_sha256: str
    fclk_hz: int
    g05: IpDescriptor
    trace: IpDescriptor
    product_clock_net: str
    product_reset_net: str
    uart: UartDescriptor

    def validate(self):
        for name in ('operation_id', 'build_id', 'boot_id', 'product_clock_net', 'product_reset_net'):
            _text(getattr(self, name))
        for name in ('request_hash', 'bit_sha256', 'hwh_sha256', 'mapping_sha256'):
            _hex(getattr(self, name))
        _need(type(self.fclk_hz) is int and self.fclk_hz == 50_000_000, 'actual product FCLK must be50MHz')
        _need(type(self.g05) is IpDescriptor and type(self.trace) is IpDescriptor, 'typed actual protected IP descriptors')
        self.g05.validate(); self.trace.validate()
        _need((self.g05.phys_addr, self.g05.addr_range) == PROTECTED[0]
              and (self.trace.phys_addr, self.trace.addr_range) == PROTECTED[1], 'protected actual mappings changed')
        _need(type(self.uart) is UartDescriptor, 'typed actual UART descriptor')
        self.uart.validate()
        _need(self.uart.clock_net == self.product_clock_net and self.uart.reset_net == self.product_reset_net,
              'UART must share verified product clock/reset')


LoadedIdentity = ProductBinding  # Descriptive compatibility alias; same exact type.


@dataclass(frozen=True)
class Profile:
    expected: LoadedIdentity
    run_id: str
    source: str

    def validate(self):
        _need(type(self.expected) is LoadedIdentity, 'typed expected identity')
        self.expected.validate(); _text(self.run_id)
        _need(self.source in ('PC_DIRECT', 'FPGA_OUTPUT', 'MANUAL'), 'declared real source mode')


@dataclass(frozen=True)
class BTransfer:
    operation_id: str
    transfer_id: str
    mcu_observation_id: str
    last_seq: int
    evidence_sha256: str
    scope: str

    def validate(self):
        for name in ('operation_id', 'transfer_id', 'mcu_observation_id'):
            _text(getattr(self, name))
        _uint(self.last_seq, 0xfffffffd)  # connect needs distinct STOP+STATUS.
        _hex(self.evidence_sha256)
        _need(self.scope in ('DIAGNOSTIC_ONLY', 'MOTION_READY'), 'explicit B transfer scope')


class RootLoadedProduct(ABC):
    """A-owned live capability, not constructible from profile JSON.

    A implements these methods in its existing sole product-init owner. It must
    read actual current generation/BOOT/build and ip_dict via its established
    verified path, and authorize authentic B READY/sequence/wiring transfer.
    Python subclassing is not cryptographic authentication. A's trusted Root
    boundary remains explicit; synthetic implementations must say simulation.
    """
    @property
    @abstractmethod
    def simulation(self) -> bool: ...

    @abstractmethod
    def read_current(self) -> ProductBinding: ...

    @abstractmethod
    def read_hwh_bytes(self) -> bytes: ...

    @abstractmethod
    def authorize_transfer(self, profile: Profile, transfer: BTransfer) -> None:
        """Raise unless current onsite wiring/no-XDS and authentic current B
        observation/unique-writer transfer/sequence/scope are genuine. MOTION_READY
        additionally requires MCU READY/OFF/unarmed; DIAGNOSTIC_ONLY permits
        STATUS/STOP only and cannot promote a FAULT snapshot to motion READY.
        """

    @abstractmethod
    def authorize_motor(self, profile: Profile, transfer: BTransfer) -> None:
        """Separate current operator authorization after observed low-speed trial."""

    @abstractmethod
    def open_uart_mmio(self, binding: ProductBinding):
        """Map only already-loaded verified UART; never load/reset/clock-change."""


def _hwh_descriptor(blob, wanted):
    _need(type(blob) is bytes and 0 < len(blob) <= 8*1024*1024, 'bounded HWH bytes')
    _need(b'<!DOCTYPE' not in blob.upper() and b'<!ENTITY' not in blob.upper(), 'HWH entity declarations forbidden')
    try:
        tree = ET.fromstring(blob)
        modules = [m for m in tree.iter('MODULE') if m.get('FULLNAME', '').strip('/') == wanted.fullname.strip('/')]
        _need(len(modules) == 1, 'unique HWH UART module')
        m = modules[0]; params = {}
        for p in m.findall('./PARAMETERS/PARAMETER'):
            key = p.get('NAME')
            _need(key not in params, 'duplicate HWH parameter')
            params[key] = p.get('VALUE')
        number = lambda key: int(params[key], 0)
        declared_ports = m.findall('./PORTS/PORT')
        ports = {p.get('NAME'): p for p in declared_ports}
        _need(len(ports) == len(declared_ports), 'duplicate HWH port')
        clock = ports['s_axi_aclk']; reset = ports['s_axi_aresetn']
        ranges = [r for r in tree.iter('MEMRANGE') if r.get('INSTANCE') == m.get('INSTANCE')
                  and r.get('SLAVEBUSINTERFACE') == 'S_AXI']
        _need(len(ranges) == 1, 'unique HWH UART memory range')
        base, high = int(ranges[0].get('BASEVALUE'), 0), int(ranges[0].get('HIGHVALUE'), 0)
        observed = UartDescriptor(m.get('FULLNAME', '').strip('/'), m.get('VLNV'), base, high-base+1,
            number('C_S_AXI_ACLK_FREQ_HZ'), number('C_BAUDRATE'), number('C_DATA_BITS'),
            bool(number('C_USE_PARITY')), 1, clock.get('SIGNAME'), reset.get('SIGNAME'))
        observed.validate()
        _need(int(clock.get('CLKFREQUENCY'), 0) == 50_000_000
              and reset.get('POLARITY') == 'ACTIVE_LOW' and observed == wanted, 'HWH/current UART metadata mismatch')
        return observed
    except (KeyError, ValueError, TypeError, ET.ParseError) as error:
        raise ServiceError('invalid HWH UART structure') from error


class _OwnerLock:
    """Stable same-device state directory, OS lock survives file existence.

    Never deletes lock files or breaks another process's lock. A must use one
    persistent state directory for this physical UART across all operations.
    """
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open('a+b'); self.locked = False
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0)
                if not self.file.read(1):
                    self.file.write(b'0'); self.file.flush()
                self.file.seek(0); msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.locked = True
        except BaseException:
            self.file.close(); raise ServiceError('UART already has an owner')

    def close(self):
        if self.locked:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0); msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.locked = False
        self.file.close()


def _exclusive_json(path, value):
    with path.open('xb') as file:
        file.write(_raw(value)+b'\n'); file.flush(); os.fsync(file.fileno())


class _Transport:
    def __init__(self, service, uart):
        self.service, self.uart = service, uart
        self.pending = None

    def write_frame(self, frame):
        self.service._assert_current()
        if self.pending is not None:
            _need(frame[3] == 3 and self.pending[3] != 3 and self.service._session.terminal,
                  'one pending UART frame; only one distinct terminal STOP is allowed')
            self.service._log('unknown_request_before_distinct_stop', request_hex=self.pending.hex())
        self.service._log('uart_write_intent', frame_hex=bytes(frame).hex())
        self.pending = bytes(frame)
        try:
            self.uart.write_frame(frame)
        except BaseException as error:
            self.service._log('uart_write_error_unknown', error=type(error).__name__+': '+str(error))
            raise

    def read_frame(self, timeout):
        try:
            reply = self.uart.read_frame(timeout)
            self.service._assert_current()
        except BaseException as error:
            self.service._log('uart_read_error_unknown', error=type(error).__name__+': '+str(error))
            raise
        self.service._log('uart_reply_bytes', request_hex=self.pending.hex() if self.pending else None,
                          reply_hex=bytes(reply).hex() if reply is not None else None)
        self.pending = None
        return reply


class _SingleStopSession(CompoundDeltaSession):
    """Reuse baseline wire operations while coalescing all terminal STOP tails."""
    def __init__(self, *args, diagnostic=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.diagnostic = diagnostic
        self.connecting = False; self.request_kind = None
        self.terminal = False; self.stop_attempted = False
        self.stop_reply = None; self.stop_error = None

    def _send(self, *args, **kwargs):
        try:
            recover_idle_watchdog = kwargs.pop('_delta_recover_idle_watchdog', False)
            _need(type(recover_idle_watchdog) is bool and (not recover_idle_watchdog
                  or args[0] == 4 and kwargs.get('require_ok') is False),
                  'private delta recovery is only a non-required-OK STATUS')
            reply = super()._send(*args, **kwargs)
            diagnostic_disarmed = self.diagnostic and args[0] in (3, 4) and reply.result_code == 3
            idle_watchdog = (recover_idle_watchdog and reply.result_code == 7
                             and not reply.armed and reply.requested_duty_permille == 0)
            _need(reply.result_code == 0 or diagnostic_disarmed or idle_watchdog, 'MCU non-OK response')
            if args[0] == 3:
                _need(not reply.armed and reply.requested_duty_permille == 0, 'STOP reply is not disarmed/OFF')
            return reply
        except BaseException:
            self.terminal = True
            raise

    def _motor_send(self, *args, **kwargs):
        try:
            return super()._motor_send(*args, **kwargs)
        except BaseException:
            self.terminal = True
            raise

    def stop(self):
        # A baseline validation failure marks failed before its STOP tail.
        # Such a tail is terminal even if the rejected intent looked like0OFF.
        normal_off = not self.terminal and not self.failed and (self.connecting or self.request_kind == 'motor_zero')
        if normal_off:
            try:
                return super().stop()
            except BaseException as error:
                # An unknown STOP is itself the terminal attempt, never resent.
                self.terminal = self.stop_attempted = True; self.stop_error = error
                raise
        self.terminal = True
        if self.stop_attempted:
            if self.stop_error is not None:
                raise self.stop_error
            return self.stop_reply
        self.stop_attempted = True
        try:
            self.stop_reply = super().stop()
            return self.stop_reply
        except BaseException as error:
            self.stop_error = error
            raise

    def connect(self):
        self.connecting = True
        try:
            return super().connect()
        finally:
            self.connecting = False

    def handle(self, request):
        _need(not self.terminal, 'terminal session; fresh explicit transfer required')
        self.request_kind = ('motor_zero' if type(request) is dict and request.get('op') == 'motor'
                             and request.get('speed_pct') == 0 else request.get('op') if type(request) is dict else None)
        try:
            return super().handle(request)
        finally:
            self.request_kind = None


class ProductUartService:
    """One foreground IO owner. No background keepalive or native RPC consumer."""
    def __init__(self):
        raise ServiceError('Use attach with the already-loaded Root capability')

    @classmethod
    def attach(cls, root, profile, transfer, state_dir, *, clock=time.monotonic, sleep=time.sleep):
        _verify_dependencies()
        _need(isinstance(root, RootLoadedProduct), 'live Root capability required; JSON is not authority')
        _need(type(root.simulation) is bool, 'explicit simulation scope')
        _need(type(profile) is Profile and type(transfer) is BTransfer, 'typed profile and transfer')
        profile.validate(); transfer.validate()
        _need(transfer.operation_id == profile.expected.operation_id, 'transfer operation mismatch')
        self = object.__new__(cls)
        self.root, self.profile, self.transfer, self.clock = root, profile, transfer, clock
        self._owner = threading.get_ident(); self._closed = False; self._lock = None; self._audit = None
        self._identity_poisoned = False
        self._session = None; self._client = None; self._stop_attempted = False
        self._stop_reply = None; self._stop_error = None; self._mmio = None
        self._assert_current()
        hwh = root.read_hwh_bytes()
        _need(type(hwh) is bytes and hashlib.sha256(hwh).hexdigest() == profile.expected.hwh_sha256, 'matching HWH SHA256 required')
        _hwh_descriptor(hwh, profile.expected.uart)
        state = Path(state_dir)
        _need(state.is_absolute(), 'Root supplies one persistent absolute UART state directory')
        try:
            self._lock = _OwnerLock(state/'mcu_uart.owner.lock')
            self._assert_current()
            _need(root.authorize_transfer(profile, transfer) is None, 'Root authorization must return normally, not a boolean flag')
            opkey = hashlib.sha256(profile.expected.operation_id.encode('ascii')).hexdigest()
            run = state/'operations'/opkey; run.mkdir(parents=True, exist_ok=False)
            self._audit = (run/'uart-events.jsonl').open('xb', buffering=0)
            self._log('transfer_consumption_intent', profile=asdict(profile), transfer=asdict(transfer))
            used = state/'consumed-transfers'; used.mkdir(exist_ok=True)
            _exclusive_json(used/(transfer.evidence_sha256+'.json'), dict(profile=asdict(profile), transfer=asdict(transfer)))
            _exclusive_json(run/'binding.json', dict(profile=asdict(profile), transfer=asdict(transfer)))
            journal = SequenceJournal(run/'sequence.json', initialize=transfer.last_seq+1)
            self._assert_current()
            d = profile.expected.uart
            self._mmio = root.open_uart_mmio(profile.expected)
            self._uart = UartLite(self._mmio, clock=clock, sleep=sleep)
            status = self._mmio.read(UartLite.STATUS)
            _need(type(status) is int and status & 0xfb == 0 and status & 4,
                  'new UART must be idle/empty/error-free; never auto-flush unknown bytes')
            self._transport = _Transport(self, self._uart)
            self._session = _SingleStopSession(self._transport, journal, source=profile.source, clock=clock,
                simulation=root.simulation, allow_motor=False,
                diagnostic=transfer.scope == 'DIAGNOSTIC_ONLY',
                physical_path='A existing product -> dedicated AXI UARTLite -> G3507 UART1')
            self._client = SessionClient(self._session)
            connected = self._session.connect()  # STOP+STATUS only, never ARM.
            status = connected['status']
            self.mcu_feedback_ready = (status['result_code'] == 0 and status['last_joho_error'] == 0
                and status['yaw_feedback']['fresh'] is True and status['pitch_feedback']['fresh'] is True
                and status['armed'] is False and status['requested_duty_permille'] == 0)
            self.connection = dict(connected, event='uart_connected', transfer_scope=transfer.scope,
                                   mcu_feedback_ready_observed=self.mcu_feedback_ready,
                                   actuator_READY_authorized=transfer.scope == 'MOTION_READY')
            if transfer.scope == 'MOTION_READY':
                _need(self.mcu_feedback_ready, 'motion transfer lacks current healthy feedback')
            self._log('connected_without_motor', connection=self.connection)
            return self
        except BaseException as error:
            if self._session is not None:
                try:
                    self.stop('attach_failure')
                except BaseException:
                    pass
            self._release()
            raise

    def _assert_current(self):
        _need(threading.get_ident() == self._owner and not self._closed, 'one foreground UART owner')
        _need(not self._identity_poisoned, 'loaded identity uncertainty latched; no automatic reuse')
        try:
            actual = self.root.read_current()
            _need(type(actual) is LoadedIdentity, 'Root must read typed actual loaded identity')
            actual.validate()
            _need(actual == self.profile.expected, 'loaded product changed; no write to another generation')
        except BaseException:
            self._identity_poisoned = True
            raise

    def _log(self, event, **fields):
        if self._audit is not None:
            self._audit.write(_raw(dict(event=event, monotonic_ns=time.monotonic_ns(),
                operation_id=self.profile.expected.operation_id, simulation=self.root.simulation,
                requirements_sha256=REQUIREMENTS_SHA256, **fields))+b'\n')
            os.fsync(self._audit.fileno())

    def _call(self, method, *args, **kwargs):
        self._assert_current()
        _need(not self._stop_attempted and not self._session.terminal, 'terminal no replay')
        try:
            reply = getattr(self._client, method)(*args, **kwargs)
            self._log('client_result', result=reply)
            return reply
        except BaseException:
            try:
                self.stop('client_failure')
            except BaseException:
                pass
            raise

    def delta(self, command_seq, run_id, yaw_delta_cd, pitch_delta_cd, speed_delta_permille,
              *, move_ms=500, lease_ms=300, flags=1, source_valid_for_ms):
        self._require_motion()
        return self._call('delta',command_seq,run_id,yaw_delta_cd,pitch_delta_cd,speed_delta_permille,
            move_ms=move_ms,lease_ms=lease_ms,flags=flags,source_valid_for_ms=source_valid_for_ms)

    def delta_keepalive(self, command_seq, run_id, *, lease_ms=300):
        self._require_motion()
        return self._call('delta_keepalive',command_seq,run_id,lease_ms=lease_ms)

    def startup_prepare(self, run_id, initial_speed_permille, move_ms=500):
        self._require_motion()
        return self._call('startup_prepare', run_id, initial_speed_permille, move_ms)

    def pose(self, *args, **kwargs):
        self._require_motion()
        return self._call('pose', *args, **kwargs)

    def motor(self, speed_pct):
        self._require_motion()
        return self._call('motor', speed_pct)

    def keepalive(self):
        self._require_motion()
        return self._call('keepalive')

    def status(self):
        return self._call('_call', 'status')

    def _require_motion(self):
        _need(self.transfer.scope == 'MOTION_READY' and self.mcu_feedback_ready,
              'diagnostic transfer cannot ARM/pose/motor/follow')

    def enable_motor(self):
        self._require_motion()
        self._assert_current()
        _need(not self._stop_attempted and not self._session.terminal, 'terminal no motor enable')
        _need(self.root.authorize_motor(self.profile, self.transfer) is None, 'separate Root motor authorization required')
        self._session.allow_motor = True
        self._log('motor_permission_enabled_no_command')

    def make_follower(self, reference_xyzw, *, limits=Limits(), motor_enabled=False, clock_ns=time.perf_counter_ns):
        self._require_motion()
        self._assert_current()
        _need(type(motor_enabled) is bool and (not motor_enabled or self._session.allow_motor), 'motor enable remains explicit')
        return Follower(self, FollowMapper(self.profile.run_id, self.profile.source, reference_xyzw, limits),
                        motor_enabled=motor_enabled, clock_ns=clock_ns)

    def stop(self, reason='explicit_stop'):
        _need(threading.get_ident() == self._owner, 'one foreground UART owner')
        if self._stop_attempted:
            if self._stop_error is not None:
                raise self._stop_error
            return self._stop_reply
        self._stop_attempted = True
        try:
            self._assert_current()  # Never safety-write into a reloaded product.
            self._log('terminal_stop_intent', reason=reason)
            self._session.terminal = True
            reply = self._session.stop()
            self._stop_reply = self._session.record(reply, 'stop')
            self._log('terminal_stop_result', result=self._stop_reply)
            return self._stop_reply
        except BaseException as error:
            self._stop_error = error
            self._log('terminal_stop_error', reason=reason, error=type(error).__name__+': '+str(error))
            raise

    def _release(self):
        if self._audit is not None:
            self._audit.close(); self._audit = None
        if self._lock is not None:
            self._lock.close(); self._lock = None
        self._closed = True

    def close(self):
        if self._closed:
            return
        try:
            self.stop('close')
        finally:
            self._release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


__all__ = ['BTransfer', 'IpDescriptor', 'LoadedIdentity', 'ProductBinding', 'Profile',
           'ProductUartService', 'RootLoadedProduct', 'ServiceError', 'UartDescriptor']
